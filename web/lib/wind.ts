export type WindVector = {
  lat: number;
  lon: number;
  wind_speed: number | null;
  wind_dir: number | null;
};
export type Segment = {
  from: [number, number];
  to: [number, number];
  speed: number;
};

const HEAD = 0.3;

/**
 * Tiga segmen per vektor: batang berpusat di titik, dua sisi kepala di ujung arah tiupan.
 * degPerKmh: panjang panah dalam derajat per km/jam, MapView menurunkannya dari zoom.
 */
export function windArrows(
  vectors: WindVector[],
  degPerKmh: number,
): Segment[] {
  const segments: Segment[] = [];
  for (const { lat, lon, wind_speed: speed, wind_dir: dir } of vectors) {
    if (speed == null || dir == null || speed <= 0) continue;
    // wind_dir meteorologis: arah asal angin, jadi panah menunjuk ke dir + 180.
    const bearing = ((dir + 180) * Math.PI) / 180;
    const length = speed * degPerKmh;
    const scaleLon = 1 / Math.cos((lat * Math.PI) / 180);
    const offset = (angle: number, len: number): [number, number] => [
      Math.sin(angle) * len * scaleLon,
      Math.cos(angle) * len,
    ];
    const [dx, dy] = offset(bearing, length / 2);
    const tip: [number, number] = [lon + dx, lat + dy];
    segments.push({ from: [lon - dx, lat - dy], to: tip, speed });
    for (const side of [-1, 1]) {
      const [hx, hy] = offset(
        bearing + Math.PI + (side * Math.PI) / 6,
        length * HEAD,
      );
      segments.push({ from: tip, to: [tip[0] + hx, tip[1] + hy], speed });
    }
  }
  return segments;
}
