"""
Binary .scenec writer — matches the exact C struct layout used by JellyCar.

Struct sizes (verified via offsetof on x86-64):
  BodyObjectInfo = 108 bytes
  BodyPoint      = 12 bytes
  BodySpring     = 16 bytes
  BodyPolygon    = 12 bytes  (indices stored as floats!)
  GameObject     = 112 bytes
"""

import struct

# Verified format strings (little-endian, with explicit padding)
BOI_FMT = '<64s fff fff BB 2x ff B 3x f'   # 108 bytes
GO_FMT  = '<64s fffff i BB 2x ffff f'       # 112 bytes
BP_FMT  = '<fff'                             # 12 bytes  (x, y, mass)
BS_FMT  = '<iiff'                            # 16 bytes  (pt1, pt2, k, damp)
BPOLY_FMT = '<fff'                           # 12 bytes  (indices as floats)


def _encode_name(name: str) -> bytes:
    b = name.encode('utf-8')[:63]
    return b.ljust(64, b'\x00')


def pack_body_object_info(name, colorR, colorG, colorB,
                          massPerPoint, edgeK, edgeDamping,
                          isKinematic, shapeMatching, shapeK, shapeDamping,
                          pressureized, pressure) -> bytes:
    return struct.pack(BOI_FMT,
        _encode_name(name),
        colorR, colorG, colorB,
        massPerPoint, edgeK, edgeDamping,
        int(isKinematic), int(shapeMatching),
        shapeK, shapeDamping,
        int(pressureized), pressure)


def pack_body_point(x, y, mass=-1.0) -> bytes:
    return struct.pack(BP_FMT, x, y, mass)


def pack_body_spring(pt1, pt2, k, damp) -> bytes:
    return struct.pack(BS_FMT, pt1, pt2, k, damp)


def pack_body_polygon(i0, i1, i2) -> bytes:
    # Indices stored as floats in the file
    return struct.pack(BPOLY_FMT, float(i0), float(i1), float(i2))


def pack_game_object(name, posX, posY, angle, scaleX, scaleY, material,
                     isPlatform=False, isMotor=False,
                     platformOffsetX=0.0, platformOffsetY=0.0,
                     platformSecondsPerLoop=0.0, platformStartOffset=0.0,
                     motorRadiansPerSecond=0.0) -> bytes:
    return struct.pack(GO_FMT,
        _encode_name(name),
        posX, posY, angle, scaleX, scaleY,
        material,
        int(isPlatform), int(isMotor),
        platformOffsetX, platformOffsetY, platformSecondsPerLoop, platformStartOffset,
        motorRadiansPerSecond)


def write_scenec(path: str, bodies: list, objects: list,
                 car_name: str, car_x: float, car_y: float,
                 finish_x: float, finish_y: float, fall_line: float):
    """
    bodies: list of dicts with keys:
        name, colorR, colorG, colorB, massPerPoint, edgeK, edgeDamping,
        isKinematic, shapeMatching, shapeK, shapeDamping, pressureized, pressure,
        points: [(x,y,mass), ...],
        springs: [(pt1,pt2,k,damp), ...],
        polygons: [(i0,i1,i2), ...]

    objects: list of dicts with keys:
        name (must match a body name), posX, posY, angle, scaleX, scaleY, material,
        isPlatform, isMotor, platformOffsetX, platformOffsetY,
        platformSecondsPerLoop, platformStartOffset, motorRadiansPerSecond
    """
    with open(path, 'wb') as f:
        # Number of body definitions
        f.write(struct.pack('<i', len(bodies)))

        for b in bodies:
            f.write(pack_body_object_info(
                b['name'], b.get('colorR', 0.5), b.get('colorG', 0.5), b.get('colorB', 0.5),
                b.get('massPerPoint', 0.0), b.get('edgeK', 100.0), b.get('edgeDamping', 1.0),
                b.get('isKinematic', False), b.get('shapeMatching', True),
                b.get('shapeK', 100.0), b.get('shapeDamping', 10.0),
                b.get('pressureized', False), b.get('pressure', 0.0)
            ))
            pts = b.get('points', [])
            f.write(struct.pack('<i', len(pts)))
            for (x, y, mass) in pts:
                f.write(pack_body_point(x, y, mass))

            springs = b.get('springs', [])
            f.write(struct.pack('<i', len(springs)))
            for (pt1, pt2, k, damp) in springs:
                f.write(pack_body_spring(pt1, pt2, k, damp))

            polys = b.get('polygons', [])
            f.write(struct.pack('<i', len(polys)))
            for (i0, i1, i2) in polys:
                f.write(pack_body_polygon(i0, i1, i2))

        # Game objects
        f.write(struct.pack('<i', len(objects)))
        for o in objects:
            f.write(pack_game_object(
                o['name'], o.get('posX', 0.0), o.get('posY', 0.0),
                o.get('angle', 0.0), o.get('scaleX', 1.0), o.get('scaleY', 1.0),
                o.get('material', 0),
                o.get('isPlatform', False), o.get('isMotor', False),
                o.get('platformOffsetX', 0.0), o.get('platformOffsetY', 0.0),
                o.get('platformSecondsPerLoop', 0.0), o.get('platformStartOffset', 0.0),
                o.get('motorRadiansPerSecond', 0.0)
            ))

        # Car name (64 bytes) + position
        f.write(_encode_name(car_name))
        f.write(struct.pack('<ff', car_x, car_y))

        # Finish + fall line
        f.write(struct.pack('<fff', finish_x, finish_y, fall_line))
