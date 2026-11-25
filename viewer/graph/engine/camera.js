// Camera arithmetic. Pure: no DOM. A camera is {k, tx, ty}: world point (x, y) shows at (tx + k*x, ty + k*y).

export const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

/* The camera that shows the world rectangle (x, y, w, h) centred in a viewport {w, h}, at most scale kmax. */
export function frame(vp, x, y, w, h, kmax, pad, kmin) {
  const k = clamp(Math.min((vp.w - 2 * pad) / w, (vp.h - 2 * pad) / h), kmin, kmax);
  return { k, tx: (vp.w - w * k) / 2 - x * k, ty: Math.max(pad, (vp.h - h * k) / 2) - y * k };
}

/* Scale by factor f about the screen point (sx, sy), keeping the world point under it fixed. */
export function zoomAbout(cam, sx, sy, f, kmin, kmax) {
  const k2 = clamp(cam.k * f, kmin, kmax), wx = (sx - cam.tx) / cam.k, wy = (sy - cam.ty) / cam.k;
  return { k: k2, tx: sx - wx * k2, ty: sy - wy * k2 };
}

export const toWorld = (cam, sx, sy) => ({ x: (sx - cam.tx) / cam.k, y: (sy - cam.ty) / cam.k });
