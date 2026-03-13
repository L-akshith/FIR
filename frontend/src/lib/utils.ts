/**
 * Fuzz GPS coordinates within a ~2.5km radius circle.
 * Real farm location never leaves the client device.
 */
export function fuzzCoordinates(lat: number, lon: number): { lat: number; lon: number } {
  const radiusKm = 2.5;
  const earthRadiusKm = 6371;

  const angle = Math.random() * 2 * Math.PI;
  const distance = Math.random() * radiusKm;

  const deltaLat = (distance / earthRadiusKm) * (180 / Math.PI);
  const deltaLon =
    (distance / (earthRadiusKm * Math.cos((lat * Math.PI) / 180))) *
    (180 / Math.PI);

  return {
    lat: lat + deltaLat * Math.cos(angle),
    lon: lon + deltaLon * Math.sin(angle),
  };
}

/**
 * Generate a SHA-256 hash of a phone number.
 * The raw phone number is never stored or transmitted.
 */
export async function generateFarmerHash(phone: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(phone);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Compress an image file to target size using Canvas API.
 */
export async function compressImage(
  file: File,
  maxKB = 300
): Promise<File> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);

    img.onload = () => {
      URL.revokeObjectURL(url);

      const canvas = document.createElement('canvas');
      const maxDim = 1024;
      let { width, height } = img;

      if (width > maxDim || height > maxDim) {
        const ratio = Math.min(maxDim / width, maxDim / height);
        width = Math.round(width * ratio);
        height = Math.round(height * ratio);
      }

      canvas.width = width;
      canvas.height = height;

      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reject(new Error('Canvas context unavailable'));
        return;
      }

      ctx.drawImage(img, 0, 0, width, height);

      let quality = 0.85;
      const tryCompress = () => {
        canvas.toBlob(
          (blob) => {
            if (!blob) {
              reject(new Error('Compression failed'));
              return;
            }

            if (blob.size > maxKB * 1024 && quality > 0.3) {
              quality -= 0.1;
              tryCompress();
            } else {
              resolve(
                new File([blob], file.name, {
                  type: 'image/jpeg',
                  lastModified: Date.now(),
                })
              );
            }
          },
          'image/jpeg',
          quality
        );
      };

      tryCompress();
    };

    img.onerror = () => reject(new Error('Image load failed'));
    img.src = url;
  });
}

/**
 * Detect blur using Laplacian variance on image data.
 * Returns true if the image is sharp enough.
 */
export function checkImageSharpness(imageData: ImageData): boolean {
  const gray = new Float32Array(imageData.width * imageData.height);
  const data = imageData.data;

  for (let i = 0; i < gray.length; i++) {
    gray[i] = 0.299 * data[i * 4] + 0.587 * data[i * 4 + 1] + 0.114 * data[i * 4 + 2];
  }

  let variance = 0;
  const w = imageData.width;

  for (let y = 1; y < imageData.height - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const idx = y * w + x;
      const laplacian =
        -gray[idx - w] - gray[idx - 1] + 4 * gray[idx] - gray[idx + 1] - gray[idx + w];
      variance += laplacian * laplacian;
    }
  }

  variance /= gray.length;
  return variance > 100;
}

/**
 * Check mean brightness of an image.
 * Returns value 0-255. Acceptable range: 50-220.
 */
export function checkBrightness(imageData: ImageData): number {
  let total = 0;
  const data = imageData.data;

  for (let i = 0; i < data.length; i += 4) {
    total += 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
  }

  return total / (data.length / 4);
}

/**
 * Calculate green coverage percentage.
 * Returns 0-100. Minimum required: 55%.
 */
export function checkGreenCoverage(imageData: ImageData): number {
  let greenPixels = 0;
  const data = imageData.data;
  const totalPixels = data.length / 4;

  for (let i = 0; i < data.length; i += 4) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];

    if (g > r && g > b && g > 60) {
      greenPixels++;
    }
  }

  return (greenPixels / totalPixels) * 100;
}
