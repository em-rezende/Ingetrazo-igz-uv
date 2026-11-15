# =========================================================================
# Pasta: igz-UV/core/
# Arquivo: transforms.py
# Descrição: Composição de transformações afins em UV (offset, escala, rotação).
# =========================================================================
from .texture import uv_at


def compose_uvw(uvw0, cu, cv, scale_u, scale_v, ca, sa, du, dv):
    """Compõe nova uvw aplicando escala anisotrópica, rotação e offset
    em torno do centro UV (cu, cv). Devolve [gu.xyz, u0, gv.xyz, v0]."""
    P0 = (0.0, 0.0, 0.0)
    P1 = (1.0, 0.0, 0.0)
    P2 = (0.0, 1.0, 0.0)
    P3 = (0.0, 0.0, 1.0)

    def composto(P):
        u0, v0 = uv_at(uvw0, P)
        u = cu + (u0 - cu) * scale_u
        v = cv + (v0 - cv) * scale_v
        x = u - cu
        y = v - cv
        u = cu + ca * x - sa * y
        v = cv + sa * x + ca * y
        return (u + du, v + dv)

    u0, v0 = composto(P0)
    u1, v1 = composto(P1)
    u2, v2 = composto(P2)
    u3, v3 = composto(P3)

    return [u1 - u0, u2 - u0, u3 - u0, u0,
            v1 - v0, v2 - v0, v3 - v0, v0]