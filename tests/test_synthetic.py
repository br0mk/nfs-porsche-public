"""Tests using inputs constructed here, without bytes copied from game files."""
import json
import struct

import numpy as np
import pytest

from nfs5 import cardb, crp, export, fsh, ini, loc, refpack, sim


def test_refpack_literals_and_overlap():
    stream = bytes.fromhex('10 fb 00 00 08 e0 41 42 43 44 00 03 fd 45')
    assert refpack.decompress(stream) == b'ABCDABCE'
    overlap = bytes.fromhex('10 fb 00 00 08 e0 41 41 41 41 00 00 fd 42')
    assert refpack.decompress(overlap) == b'AAAAAAAB'


@pytest.mark.parametrize('n', range(4))
def test_refpack_trailing_literals(n):
    payload = b'xyz'[:n]
    data = bytes([0x10, 0xFB]) + n.to_bytes(3, 'big') + bytes([0xFC + n]) + payload
    assert refpack.decompress(data) == payload


def test_refpack_rejects_invalid_header_and_size():
    with pytest.raises(ValueError, match='not a RefPack'):
        refpack.decompress(b'plain text')
    with pytest.raises(ValueError, match='size mismatch'):
        refpack.decompress(bytes.fromhex('10 fb 00 00 01 fc'))


def test_ini_sections_and_values():
    assert ini.parse('; note\r\n[part]\r\na = x=y\r\n[part]\nb=2\r\n') == {
        'part': {'a': 'x=y', 'b': '2'}}


def test_synthetic_car_record():
    data = bytearray(cardb.RECORD)
    for offset, value in [(2, b'Example'), (77, b'card'), (127, b'model'), (177, b'sim')]:
        data[offset:offset + len(value)] = value
    assert cardb.parse(bytes(data)) == [cardb.CarEntry('Example', 'card', 'model', 'sim')]
    with pytest.raises(ValueError):
        cardb.parse(b'incomplete')


def test_synthetic_sim_curve_and_unknown_fields():
    data = bytearray(sim.SIZE)
    data[:7] = b'Example'
    struct.pack_into('<f', data, 64, 123.5)
    struct.pack_into('<21f', data, 156, *range(21))
    struct.pack_into('<I', data, 256, 0x12345678)
    result = sim.parse(bytes(data))
    assert result['title'] == 'Example'
    assert result['mass_kg'] == 123.5
    assert result['torque_curve_lbft'] == list(range(21))
    assert result['unnamed'][256] == 0x12345678


def test_synthetic_loc_strings():
    strings = b'Alpha\0Beta\0'
    block = b'LOCL' + struct.pack('<III', 24 + len(strings), 0, 2)
    block += struct.pack('<II', 24, 30) + strings
    data = b'LOCH' + struct.pack('<IIII', 20, 1, 1, 20) + block
    assert loc.parse(data) == [['Alpha', 'Beta']]


def test_synthetic_fsh_bgra_pixel():
    block = bytes([0x7D, 0, 0, 0]) + struct.pack('<6H', 1, 1, 0, 0, 0, 0)
    block += bytes([30, 20, 10, 255])
    data = b'SHPI' + struct.pack('<II4s', 24 + len(block), 1, b'TEST')
    data += struct.pack('<4sI', b'pix0', 24) + block
    archive = fsh.parse(data)
    assert archive.dir_id == 'TEST'
    assert fsh.entry_rgba(archive.by_name('pix0')).tolist() == [[[10, 20, 30, 255]]]


def test_synthetic_dxt1_transparent_pixel():
    entry = fsh.Entry('test', 0x60, 4, 4, (0, 0), (0, 0), struct.pack('<HHI', 0, 0xFFFF, 3))
    pixels = fsh.entry_rgba(entry)
    assert pixels[0, 0].tolist() == [0, 0, 0, 0]
    assert pixels[0, 1].tolist() == [0, 0, 0, 255]


def test_empty_crp_and_strip_order():
    empty = crp.parse(struct.pack('<4sIII', b' raC', 0x1A, 0, 0))
    assert not empty.articles and not empty.misc
    prim = crp.Primitive(0, 0, 4, 0, (), {}, np.array([0, 1, 2, 3], np.uint8), np.arange(4))
    assert crp.corner_order(prim).tolist() == [0, 1, 2, 2, 1, 3]
    prim.vertex_indices = np.array([0, 1, 1, 2], np.uint8)
    assert crp.corner_order(prim).tolist() == []


def test_synthetic_triangle_glb(tmp_path):
    target = tmp_path / 'triangle.glb'
    batch = {'p': np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], np.float32),
             't': np.zeros((3, 2), np.float32), 'rgba': np.full((1, 1, 4), 255, np.uint8),
             'mode': 'OPAQUE'}
    assert export.write_glb_batches(target, 'Synthetic triangle', [batch]) == 1
    data = target.read_bytes()
    magic, version, length = struct.unpack_from('<III', data)
    assert (magic, version, length) == (0x46546C67, 2, len(data))
    size, kind = struct.unpack_from('<II', data, 12)
    assert kind == 0x4E4F534A
    model = json.loads(data[20:20 + size])
    assert model['asset']['version'] == '2.0'
    assert model['accessors'][0]['count'] == 3
    assert model['images'][0]['mimeType'] == 'image/png'
