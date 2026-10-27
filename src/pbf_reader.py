"""Streaming reader for the documented OSM PBF binary format; no network.

Compiled Protocol Buffers decoding skips fields we do not need. Format field
numbers below come from the OSM schema; they are not geographic settings.
"""
import struct
import zlib
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
import config


def schemas(nodes=False):
    file = descriptor_pb2.FileDescriptorProto(name="local.proto", package="pbf", syntax="proto2")
    def message(name, fields):
        msg = file.message_type.add(name=name)
        for name, number, kind, repeated, target in fields:
            field = msg.field.add(name=name, number=number, type=kind, label=3 if repeated else 1)
            if target:
                field.type_name = ".pbf." + target
    message("BlobHeader", [("type",1,9,False,None),("datasize",3,5,False,None)])
    message("Blob", [("raw",1,12,False,None),("raw_size",2,5,False,None),("zlib_data",3,12,False,None)])
    message("Header", [("required_features",4,9,True,None),("writingprogram",16,9,False,None),("replication_timestamp",32,3,False,None)])
    message("Strings", [("s",1,12,True,None)])
    if nodes:
        message("Node", [("id",1,18,False,None),("keys",2,13,True,None),("vals",3,13,True,None),("lat",8,18,False,None),("lon",9,18,False,None)])
        message("Dense", [("id",1,18,True,None),("lat",8,18,True,None),("lon",9,18,True,None),("keys_vals",10,5,True,None)])
        group = [("nodes",1,11,True,"Node"),("dense",2,11,False,"Dense")]
    else:
        message("Way", [("id",1,3,False,None),("keys",2,13,True,None),("vals",3,13,True,None),("refs",8,18,True,None)])
        message("Relation", [("id",1,3,False,None),("keys",2,13,True,None),("vals",3,13,True,None),("memids",9,18,True,None),("types",10,5,True,None)])
        group = [("ways",3,11,True,"Way"),("relations",4,11,True,"Relation")]
    message("Group", group)
    message("Block", [("strings",1,11,False,"Strings"),("groups",2,11,True,"Group"),("granularity",17,5,False,None),("lat_offset",19,3,False,None),("lon_offset",20,3,False,None)])
    pool = descriptor_pool.DescriptorPool()
    pool.Add(file)
    names = [msg.name for msg in file.message_type]
    return {name: message_factory.GetMessageClass(pool.FindMessageTypeByName("pbf."+name)) for name in names}


def blocks(path, nodes=False):
    """Reject truncated blocks instead of returning a partial successful result."""
    schema = schemas(nodes)
    with open(path, "rb") as stream:
        count = 0
        while True:
            prefix = stream.read(4)
            if not prefix:
                return
            if len(prefix) != 4:
                raise ValueError("Truncated PBF header length")
            size = struct.unpack(">I", prefix)[0]
            if not 0 < size <= config.INDIA_PBF_MAX_BLOB_BYTES:
                raise ValueError("Invalid PBF header size")
            data = stream.read(size)
            if len(data) != size:
                raise ValueError("Truncated PBF header")
            header = schema["BlobHeader"].FromString(data)
            if not 0 < header.datasize <= config.INDIA_PBF_MAX_BLOB_BYTES:
                raise ValueError("Invalid PBF blob size")
            data = stream.read(header.datasize)
            if len(data) != header.datasize:
                raise ValueError("Truncated PBF blob")
            blob = schema["Blob"].FromString(data)
            if blob.HasField("raw"):
                raw = blob.raw
            elif blob.HasField("zlib_data"):
                decoder = zlib.decompressobj()
                raw = decoder.decompress(blob.zlib_data, config.INDIA_PBF_MAX_BLOB_BYTES + 1)
                if len(raw) > config.INDIA_PBF_MAX_BLOB_BYTES or not decoder.eof:
                    raise ValueError("Oversize or incomplete PBF decompression")
                if blob.HasField("raw_size") and len(raw) != blob.raw_size:
                    raise ValueError("PBF decompressed size mismatch")
            else:
                raise ValueError("Unsupported PBF compression: use raw or zlib")
            if header.type == "OSMHeader":
                info = schema["Header"].FromString(raw)
                unknown = set(info.required_features) - config.INDIA_PBF_SUPPORTED_FEATURES
                if unknown:
                    raise ValueError(f"Unsupported required PBF features: {sorted(unknown)}")
            elif header.type == "OSMData":
                count += 1
                if count % config.INDIA_PBF_PROGRESS_BLOCKS == 0:
                    print(f"PBF {'nodes' if nodes else 'ways'}: {count} blocks, {stream.tell()/path.stat().st_size:.0%}", flush=True)
                yield schema["Block"].FromString(raw)


def tags(record, strings):
    if len(record.keys) != len(record.vals):
        raise ValueError("OSM tag keys and values do not reconcile")
    return {strings[k].decode("utf-8"): strings[v].decode("utf-8") for k,v in zip(record.keys, record.vals)}


def header_metadata(path):
    """Read the source timestamp from the file, rather than trusting its name."""
    from datetime import datetime, timezone
    schema = schemas()
    with open(path, "rb") as stream:
        prefix = stream.read(4)
        if len(prefix) != 4:
            raise ValueError("Missing PBF header")
        size = struct.unpack(">I", prefix)[0]
        if not 0 < size <= config.INDIA_PBF_MAX_BLOB_BYTES:
            raise ValueError("Invalid PBF header length")
        header = schema["BlobHeader"].FromString(stream.read(size))
        if header.type != "OSMHeader":
            return {"snapshot_utc":None,"warning":"No OSMHeader timestamp in file"}
        if not 0 < header.datasize <= config.INDIA_PBF_MAX_BLOB_BYTES:
            raise ValueError("Invalid PBF header blob size")
        blob = schema["Blob"].FromString(stream.read(header.datasize))
        if blob.HasField("raw"):
            payload = blob.raw
        else:
            decoder = zlib.decompressobj()
            payload = decoder.decompress(blob.zlib_data, config.INDIA_PBF_MAX_BLOB_BYTES+1)
            if not decoder.eof or len(payload)>config.INDIA_PBF_MAX_BLOB_BYTES:
                raise ValueError("Invalid compressed PBF header")
        info = schema["Header"].FromString(payload)
        unknown = set(info.required_features)-config.INDIA_PBF_SUPPORTED_FEATURES
        if unknown:
            raise ValueError(f"Unsupported required PBF features: {sorted(unknown)}")
        return {"snapshot_utc":datetime.fromtimestamp(info.replication_timestamp,timezone.utc).isoformat() if info.HasField("replication_timestamp") else None,
                "writing_program":info.writingprogram,"required_features":list(info.required_features)}
