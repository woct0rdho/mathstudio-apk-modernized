#!/usr/bin/env python3
from __future__ import annotations

import argparse
import struct
import zipfile
from pathlib import Path


NO_INDEX = 0xFFFFFFFF
RES_STRING_POOL_TYPE = 0x0001
RES_XML_RESOURCE_MAP_TYPE = 0x0180
RES_XML_START_ELEMENT_TYPE = 0x0102
RES_XML_END_ELEMENT_TYPE = 0x0103
TYPE_STRING = 0x03
TYPE_FLOAT = 0x04
TYPE_INT_DEC = 0x10
TYPE_INT_BOOLEAN = 0x12
ANDROID_NS_URI = "http://schemas.android.com/apk/res/android"
ANDROID_MAX_ASPECT_META = "android.max_aspect"
NAME_ATTR_ID = 0x01010003
VALUE_ATTR_ID = 0x01010024
TARGET_SDK_ATTR_ID = 0x01010270
DEBUGGABLE_ATTR_ID = 0x0101000F
RESIZEABLE_ACTIVITY_ATTR_ID = 0x010104F6
MAX_ASPECT_RATIO_ATTR_ID = 0x01010560
DEFAULT_MAX_ASPECT_RATIO = 3.0


def align4(value: int) -> int:
    return (value + 3) & ~3


def parse_string_pool(data: bytes, offset: int):
    chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", data, offset)
    if chunk_type != RES_STRING_POOL_TYPE:
        raise ValueError("expected string pool")
    string_count, style_count, flags, strings_start, styles_start = struct.unpack_from(
        "<IIIII", data, offset + 8)
    utf8 = bool(flags & 0x100)
    strings = []
    offsets = [struct.unpack_from("<I", data, offset + header_size + i * 4)[0]
               for i in range(string_count)]
    base = offset + strings_start
    for string_offset in offsets:
        cursor = base + string_offset
        if utf8:
            _, cursor = read_length8(data, cursor)
            byte_len, cursor = read_length8(data, cursor)
            raw = data[cursor:cursor + byte_len]
            strings.append(raw.decode("utf-8"))
        else:
            char_len, cursor = read_length16(data, cursor)
            raw = data[cursor:cursor + char_len * 2]
            strings.append(raw.decode("utf-16le"))
    return strings, utf8, header_size, chunk_size, style_count, flags, styles_start


def read_length8(data: bytes, cursor: int) -> tuple[int, int]:
    first = data[cursor]
    cursor += 1
    if first & 0x80:
        second = data[cursor]
        cursor += 1
        return ((first & 0x7F) << 8) | second, cursor
    return first, cursor


def read_length16(data: bytes, cursor: int) -> tuple[int, int]:
    first = struct.unpack_from("<H", data, cursor)[0]
    cursor += 2
    if first & 0x8000:
        second = struct.unpack_from("<H", data, cursor)[0]
        cursor += 2
        return ((first & 0x7FFF) << 16) | second, cursor
    return first, cursor


def encode_length8(value: int) -> bytes:
    if value > 0x7F:
        return bytes([(value >> 8) | 0x80, value & 0xFF])
    return bytes([value])


def build_string_pool(strings: list[str], flags: int, style_count: int) -> bytes:
    if style_count:
        raise ValueError("style string pools are not supported")
    utf8 = bool(flags & 0x100)
    encoded = bytearray()
    offsets = []
    for value in strings:
        offsets.append(len(encoded))
        if utf8:
            raw = value.encode("utf-8")
            encoded += encode_length8(len(value))
            encoded += encode_length8(len(raw))
            encoded += raw + b"\x00"
        else:
            raw = value.encode("utf-16le")
            encoded += struct.pack("<H", len(value))
            encoded += raw + b"\x00\x00"
    while len(encoded) % 4:
        encoded.append(0)
    header_size = 28
    strings_start = header_size + len(strings) * 4
    chunk_size = strings_start + len(encoded)
    out = bytearray()
    out += struct.pack("<HHI", RES_STRING_POOL_TYPE, header_size, chunk_size)
    out += struct.pack("<IIIII", len(strings), 0, flags, strings_start, 0)
    for string_offset in offsets:
        out += struct.pack("<I", string_offset)
    out += encoded
    return bytes(out)


def find_resource_map(data: bytes, offset: int) -> tuple[int, int]:
    cursor = offset
    while cursor < len(data):
        chunk_type, _, chunk_size = struct.unpack_from("<HHI", data, cursor)
        if chunk_type == RES_XML_RESOURCE_MAP_TYPE:
            return cursor, chunk_size
        cursor += chunk_size
    raise ValueError("resource map not found")


def set_attr_int(attr: bytearray, value: int) -> None:
    struct.pack_into("<I", attr, 8, NO_INDEX)
    struct.pack_into("<HBBI", attr, 12, 8, 0, TYPE_INT_DEC, value)


def set_attr_bool(attr: bytearray, value: bool) -> None:
    struct.pack_into("<I", attr, 8, NO_INDEX)
    struct.pack_into("<HBBI", attr, 12, 8, 0, TYPE_INT_BOOLEAN,
                     0xFFFFFFFF if value else 0)


def set_attr_float(attr: bytearray, value: float) -> None:
    struct.pack_into("<I", attr, 8, NO_INDEX)
    float_bits = struct.unpack("<I", struct.pack("<f", value))[0]
    struct.pack_into("<HBBI", attr, 12, 8, 0, TYPE_FLOAT, float_bits)


def set_attr_string(attr: bytearray, value_index: int) -> None:
    struct.pack_into("<I", attr, 8, value_index)
    struct.pack_into("<HBBI", attr, 12, 8, 0, TYPE_STRING, value_index)


def set_or_add_attr(tail: bytearray, element_offset: int, namespace_index: int,
                    attr_index: int, setter) -> None:
    ext_offset = element_offset + 16
    attr_start, attr_size, attr_count = struct.unpack_from(
        "<HHH", tail, ext_offset + 8)
    attrs_offset = ext_offset + attr_start

    for i in range(attr_count):
        attr_offset = attrs_offset + i * attr_size
        attr_name = struct.unpack_from("<I", tail, attr_offset + 4)[0]
        if attr_name == attr_index:
            attr = bytearray(tail[attr_offset:attr_offset + attr_size])
            setter(attr)
            tail[attr_offset:attr_offset + attr_size] = attr
            return

    new_attr = bytearray(attr_size)
    struct.pack_into("<III", new_attr, 0, namespace_index, attr_index, NO_INDEX)
    setter(new_attr)
    insert_offset = attrs_offset + attr_count * attr_size
    tail[insert_offset:insert_offset] = new_attr
    struct.pack_into("<H", tail, ext_offset + 12, attr_count + 1)
    chunk_size = struct.unpack_from("<I", tail, element_offset + 4)[0]
    struct.pack_into("<I", tail, element_offset + 4, chunk_size + attr_size)


def make_start_element(line_number: int, namespace_index: int, name_index: int,
                       attr_size: int, attrs: list[bytes]) -> bytes:
    attr_start = 20
    attr_count = len(attrs)
    header_size = 16
    chunk_size = header_size + attr_start + attr_count * attr_size
    out = bytearray()
    out += struct.pack("<HHI", RES_XML_START_ELEMENT_TYPE, header_size, chunk_size)
    out += struct.pack("<II", line_number, NO_INDEX)
    out += struct.pack("<II", NO_INDEX, name_index)
    out += struct.pack("<HHHHHH", attr_start, attr_size, attr_count, 0, 0, 0)
    for attr in attrs:
        if len(attr) != attr_size:
            raise ValueError("attribute size mismatch")
        out += attr
    return bytes(out)


def make_end_element(line_number: int, name_index: int) -> bytes:
    return struct.pack("<HHIIIII", RES_XML_END_ELEMENT_TYPE, 16, 24,
                       line_number, NO_INDEX, NO_INDEX, name_index)


def make_attr(namespace_index: int, attr_index: int, attr_size: int, setter) -> bytes:
    attr = bytearray(attr_size)
    struct.pack_into("<III", attr, 0, namespace_index, attr_index, NO_INDEX)
    setter(attr)
    return bytes(attr)


def has_android_max_aspect_metadata(tail: bytearray, metadata_offset: int,
                                    name_index: int,
                                    android_max_aspect_index: int) -> bool:
    ext_offset = metadata_offset + 16
    attr_start, attr_size, attr_count = struct.unpack_from(
        "<HHH", tail, ext_offset + 8)
    attrs_offset = ext_offset + attr_start
    for i in range(attr_count):
        attr_offset = attrs_offset + i * attr_size
        attr_name = struct.unpack_from("<I", tail, attr_offset + 4)[0]
        attr_value = struct.unpack_from("<I", tail, attr_offset + 8)[0]
        if attr_name == name_index and attr_value == android_max_aspect_index:
            return True
    return False


def patch_uses_sdk_target(xml_tail: bytes, strings, target_index: int,
                          target_sdk: int) -> bytes:
    tail = bytearray(xml_tail)
    uses_sdk_index = strings.index("uses-sdk")
    android_ns_index = strings.index(ANDROID_NS_URI)
    patched = 0
    offset = 0
    while offset < len(tail):
        chunk_type, _, chunk_size = struct.unpack_from("<HHI", tail, offset)
        if chunk_type == RES_XML_START_ELEMENT_TYPE:
            ext_offset = offset + 16
            element_name = struct.unpack_from("<I", tail, ext_offset + 4)[0]
            if element_name == uses_sdk_index:
                set_or_add_attr(tail, offset, android_ns_index, target_index,
                                lambda attr: set_attr_int(attr, target_sdk))
                patched += 1
                chunk_size = struct.unpack_from("<I", tail, offset + 4)[0]
        offset += chunk_size
    if not patched:
        raise ValueError("uses-sdk element not found in manifest")
    return bytes(tail)


def patch_application_debuggable(xml_tail: bytes, strings, debuggable_index: int,
                                 debuggable: bool) -> bytes:
    tail = bytearray(xml_tail)
    application_index = strings.index("application")
    android_ns_index = strings.index(ANDROID_NS_URI)
    offset = 0
    while offset < len(tail):
        chunk_type, _, chunk_size = struct.unpack_from("<HHI", tail, offset)
        if chunk_type == RES_XML_START_ELEMENT_TYPE:
            ext_offset = offset + 16
            element_name = struct.unpack_from("<I", tail, ext_offset + 4)[0]
            if element_name == application_index:
                set_or_add_attr(tail, offset, android_ns_index, debuggable_index,
                                lambda attr: set_attr_bool(attr, debuggable))
                return bytes(tail)
        offset += chunk_size
    raise ValueError("application element not found in manifest")


def patch_display_compat(xml_tail: bytes, strings, resizeable_index: int,
                         max_aspect_index: int, metadata_index: int,
                         name_index: int, value_index: int,
                         android_max_aspect_index: int,
                         max_aspect_ratio: float) -> bytes:
    tail = bytearray(xml_tail)
    application_index = strings.index("application")
    activity_index = strings.index("activity")
    android_ns_index = strings.index(ANDROID_NS_URI)
    patched_starts = 0
    patched_applications = 0
    stack = []
    offset = 0
    while offset < len(tail):
        chunk_type, _, chunk_size = struct.unpack_from("<HHI", tail, offset)
        if chunk_type == RES_XML_START_ELEMENT_TYPE:
            ext_offset = offset + 16
            line_number = struct.unpack_from("<I", tail, offset + 8)[0]
            element_name = struct.unpack_from("<I", tail, ext_offset + 4)[0]
            attr_start, attr_size = struct.unpack_from("<HH", tail, ext_offset + 8)
            parent = stack[-1] if stack else None
            if element_name == metadata_index and parent and parent["name"] in (
                    application_index, activity_index):
                if has_android_max_aspect_metadata(
                        tail, offset, name_index, android_max_aspect_index):
                    parent["has_android_max_aspect"] = True
            if element_name == application_index:
                set_or_add_attr(tail, offset, android_ns_index, resizeable_index,
                                lambda attr: set_attr_bool(attr, True))
                set_or_add_attr(tail, offset, android_ns_index, max_aspect_index,
                                lambda attr: set_attr_float(attr, max_aspect_ratio))
                patched_starts += 1
                chunk_size = struct.unpack_from("<I", tail, offset + 4)[0]
            elif element_name == activity_index:
                set_or_add_attr(tail, offset, android_ns_index, resizeable_index,
                                lambda attr: set_attr_bool(attr, True))
                set_or_add_attr(tail, offset, android_ns_index, max_aspect_index,
                                lambda attr: set_attr_float(attr, max_aspect_ratio))
                patched_starts += 1
                chunk_size = struct.unpack_from("<I", tail, offset + 4)[0]
            stack.append({
                "name": element_name,
                "line_number": line_number,
                "attr_size": attr_size,
                "has_android_max_aspect": False,
            })
        elif chunk_type == RES_XML_END_ELEMENT_TYPE:
            element_name = struct.unpack_from("<I", tail, offset + 20)[0]
            if not stack:
                raise ValueError("malformed manifest element stack")
            context = stack.pop()
            if context["name"] != element_name:
                raise ValueError("malformed manifest element nesting")
            if element_name in (application_index, activity_index):
                if not context["has_android_max_aspect"]:
                    attrs = [
                        make_attr(android_ns_index, name_index, context["attr_size"],
                                  lambda attr: set_attr_string(attr, android_max_aspect_index)),
                        make_attr(android_ns_index, value_index, context["attr_size"],
                                  lambda attr: set_attr_float(attr, max_aspect_ratio)),
                    ]
                    metadata = make_start_element(context["line_number"], NO_INDEX,
                                                  metadata_index, context["attr_size"], attrs)
                    metadata += make_end_element(context["line_number"], metadata_index)
                    tail[offset:offset] = metadata
                    offset += len(metadata)
                if element_name == application_index:
                    patched_applications += 1
        offset += chunk_size
    if not patched_starts or not patched_applications:
        raise ValueError("application/activity elements not found in manifest")
    return bytes(tail)


def patch_manifest(axml: bytes, target_sdk: int, debuggable: bool,
                   max_aspect_ratio: float) -> bytes:
    xml_type, header_size, _ = struct.unpack_from("<HHI", axml, 0)
    if xml_type != 0x0003:
        raise ValueError("not a binary XML document")
    strings, utf8, _, string_pool_size, style_count, flags, _ = parse_string_pool(
        axml, header_size)
    if "targetSdkVersion" in strings:
        target_index = strings.index("targetSdkVersion")
    else:
        target_index = len(strings)
        strings.append("targetSdkVersion")
    if "debuggable" in strings:
        debuggable_index = strings.index("debuggable")
    else:
        debuggable_index = len(strings)
        strings.append("debuggable")
    extra_strings = [
        "resizeableActivity",
        "maxAspectRatio",
        "meta-data",
        "name",
        "value",
        ANDROID_MAX_ASPECT_META,
    ]
    for value in extra_strings:
        if value not in strings:
            strings.append(value)
    resizeable_index = strings.index("resizeableActivity")
    max_aspect_index = strings.index("maxAspectRatio")
    metadata_index = strings.index("meta-data")
    name_index = strings.index("name")
    value_index = strings.index("value")
    android_max_aspect_index = strings.index(ANDROID_MAX_ASPECT_META)

    new_string_pool = build_string_pool(strings, flags, style_count)
    resource_map_offset, resource_map_size = find_resource_map(axml,
                                                              header_size + string_pool_size)
    resource_ids = [struct.unpack_from("<I", axml, resource_map_offset + 8 + i * 4)[0]
                    for i in range((resource_map_size - 8) // 4)]
    while len(resource_ids) <= target_index:
        resource_ids.append(0)
    resource_ids[target_index] = TARGET_SDK_ATTR_ID
    while len(resource_ids) <= debuggable_index:
        resource_ids.append(0)
    resource_ids[debuggable_index] = DEBUGGABLE_ATTR_ID
    while len(resource_ids) <= resizeable_index:
        resource_ids.append(0)
    resource_ids[resizeable_index] = RESIZEABLE_ACTIVITY_ATTR_ID
    while len(resource_ids) <= max_aspect_index:
        resource_ids.append(0)
    resource_ids[max_aspect_index] = MAX_ASPECT_RATIO_ATTR_ID
    while len(resource_ids) <= name_index:
        resource_ids.append(0)
    resource_ids[name_index] = NAME_ATTR_ID
    while len(resource_ids) <= value_index:
        resource_ids.append(0)
    resource_ids[value_index] = VALUE_ATTR_ID

    xml_tail = axml[resource_map_offset + resource_map_size:]
    patched_tail = patch_uses_sdk_target(xml_tail, strings, target_index, target_sdk)
    if debuggable:
        patched_tail = patch_application_debuggable(
            patched_tail, strings, debuggable_index, True)
    patched_tail = patch_display_compat(
        patched_tail, strings, resizeable_index, max_aspect_index, metadata_index,
        name_index, value_index, android_max_aspect_index, max_aspect_ratio)

    resource_map = struct.pack("<HHI", RES_XML_RESOURCE_MAP_TYPE, 8,
                               8 + len(resource_ids) * 4)
    resource_map += b"".join(struct.pack("<I", value) for value in resource_ids)
    total_size = header_size + len(new_string_pool) + len(resource_map) + len(patched_tail)
    return axml[:4] + struct.pack("<I", total_size) + new_string_pool + resource_map + patched_tail


def build_unsigned_apk(original_apk: Path, shim_so: Path | None, output_apk: Path,
                       target_sdk: int, classes_dex: Path | None,
                       debuggable: bool, max_aspect_ratio: float) -> None:
    with zipfile.ZipFile(original_apk, "r") as source, zipfile.ZipFile(
            output_apk, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            if info.filename.startswith("META-INF/"):
                continue
            if info.filename == "AndroidManifest.xml":
                patched_manifest = patch_manifest(source.read(info.filename),
                                                  target_sdk, debuggable,
                                                  max_aspect_ratio)
                target.writestr(info.filename, patched_manifest)
                continue
            if info.filename == "classes.dex" and classes_dex:
                target.writestr(info.filename, classes_dex.read_bytes())
                continue
            if info.filename == "lib/armeabi/libpomegranate.so":
                if shim_so:
                    target.writestr("lib/armeabi-v7a/libpomegranate_orig.so",
                                    source.read(info.filename))
                    target.writestr("lib/armeabi-v7a/libpomegranate.so",
                                    shim_so.read_bytes())
                else:
                    target.writestr("lib/armeabi-v7a/libpomegranate.so",
                                    source.read(info.filename))
                continue
            if info.filename.startswith("lib/armeabi/"):
                if not shim_so:
                    target.writestr("lib/armeabi-v7a/" + Path(info.filename).name,
                                    source.read(info.filename))
                continue
            target.writestr(info, source.read(info.filename))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--shim", type=Path,
                        help="replace libpomegranate.so with this loader shim")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--target-sdk", type=int, default=24)
    parser.add_argument("--classes-dex", type=Path,
                        help="use this prebuilt classes.dex instead of the original")
    parser.add_argument("--debuggable", action="store_true",
                        help="set android:debuggable=true on the application")
    parser.add_argument("--max-aspect-ratio", type=float,
                        default=DEFAULT_MAX_ASPECT_RATIO,
                        help="set high-aspect-ratio manifest support")
    args = parser.parse_args()
    build_unsigned_apk(args.apk, args.shim, args.out, args.target_sdk,
                       args.classes_dex, args.debuggable, args.max_aspect_ratio)


if __name__ == "__main__":
    main()
