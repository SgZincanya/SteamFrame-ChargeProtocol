"""Render a protocol label with the current USB contract wattage using Cairo."""

import ctypes as c
from functools import lru_cache
from math import pi
import os


class TextExtents(c.Structure):
    _fields_ = [(name, c.c_double) for name in ("x", "y", "width", "height", "advance_x", "advance_y")]


@lru_cache(maxsize=1)
def cairo_api():
    lib = c.CDLL("libcairo.so.2")
    pointer, number = c.c_void_p, c.c_double
    functions = {
        "image_surface_create": (pointer, c.c_int, c.c_int, c.c_int),
        "create": (pointer, pointer), "destroy": (None, pointer), "surface_destroy": (None, pointer),
        "arc": (None, pointer, number, number, number, number, number), "close_path": (None, pointer),
        "set_source_rgba": (None, pointer, number, number, number, number), "fill": (None, pointer),
        "select_font_face": (None, pointer, c.c_char_p, c.c_int, c.c_int), "set_font_size": (None, pointer, number),
        "text_extents": (None, pointer, c.c_char_p, c.POINTER(TextExtents)),
        "move_to": (None, pointer, number, number), "show_text": (None, pointer, c.c_char_p),
        "surface_write_to_png": (c.c_int, pointer, c.c_char_p),
    }
    for name, (result, *arguments) in functions.items():
        function = getattr(lib, "cairo_" + name)
        function.argtypes = arguments
        function.restype = result
    return lib


def contract_label(protocol, full_name, watts):
    name = "USB Power Delivery" if full_name else protocol
    power = f"{watts:.1f}".removesuffix(".0")
    return f"{name} · {power} W"


def render_contract_texture(path, label, expanded_pps):
    lib = cairo_api()
    width, height = 880, 188 if expanded_pps else 134
    surface = lib.cairo_image_surface_create(0, width, height)  # ARGB32
    context = lib.cairo_create(surface)
    try:
        title = label.encode("utf-8")
        lib.cairo_select_font_face(context, b"sans-serif", 0, 1)
        lib.cairo_set_font_size(context, 51)
        bounds = TextExtents()
        lib.cairo_text_extents(context, title, c.byref(bounds))
        inset = max(18, (width - max(bounds.width, 590 if expanded_pps else 0)) / 2 - 38)
        radius = 28
        for x, y, start in ((width - inset - radius, radius + 12, -0.5),
                            (width - inset - radius, height - radius - 12, 0),
                            (inset + radius, height - radius - 12, 0.5),
                            (inset + radius, radius + 12, 1)):
            lib.cairo_arc(context, x, y, radius, start * pi, (start + 0.5) * pi)
        lib.cairo_close_path(context)
        lib.cairo_set_source_rgba(context, 22 / 255, 29 / 255, 40 / 255, 0.94)
        lib.cairo_fill(context)

        def draw(text, size, center_y, color, weight):
            lib.cairo_select_font_face(context, b"sans-serif", 0, weight)
            lib.cairo_set_font_size(context, size)
            lib.cairo_text_extents(context, text, c.byref(bounds))
            lib.cairo_set_source_rgba(context, *color, 1)
            lib.cairo_move_to(context, (width - bounds.width) / 2 - bounds.x,
                              center_y - bounds.height / 2 - bounds.y)
            lib.cairo_show_text(context, text)

        draw(title, 51, 64 if expanded_pps else height / 2, (1, 1, 1), 1)
        if expanded_pps:
            draw(b"Programmable Power Supply (PPS)", 34, 125, (0.85, 0.91, 0.95), 0)
        status = lib.cairo_surface_write_to_png(surface, os.fsencode(path))
        if status:
            raise RuntimeError(f"Cairo PNG rendering failed ({status})")
    finally:
        lib.cairo_destroy(context)
        lib.cairo_surface_destroy(surface)
