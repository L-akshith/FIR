const API_BASE = '/api';

export async function submitReport(
  file: File,
  latitude: number,
  longitude: number,
  cropStage: string,
  userId: string
) {
  const formData = new FormData();
  formData.append('image', file);
  formData.append('latitude', latitude.toString());
  formData.append('longitude', longitude.toString());
  formData.append('crop_stage', cropStage);
  formData.append('farmer_hash', userId);

  const response = await fetch(`${API_BASE}/report`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Report submission failed: ${response.statusText}`);
  }

  return response.json();
}

export async function fetchMapData(lat: number, lon: number, radius = 100) {
  const params = new URLSearchParams({
    lat: lat.toString(),
    lon: lon.toString(),
    radius: radius.toString(),
  });

  const response = await fetch(`${API_BASE}/map?${params}`);
  if (!response.ok) {
    throw new Error(`Map data fetch failed: ${response.statusText}`);
  }

  return response.json();
}

export async function checkRisk(lat: number, lon: number) {
  const params = new URLSearchParams({
    lat: lat.toString(),
    lon: lon.toString(),
  });

  const response = await fetch(`${API_BASE}/check-risk?${params}`);
  if (!response.ok) {
    throw new Error(`Risk check failed: ${response.statusText}`);
  }

  return response.json();
}

export async function registerDevice(
  userId: string,
  fcmToken: string,
  latitude?: number,
  longitude?: number
) {
  const response = await fetch(`${API_BASE}/register-device`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      farmer_hash: userId,
      fcm_token: fcmToken,
      latitude,
      longitude,
    }),
  });

  if (!response.ok) {
    throw new Error(`Device registration failed: ${response.statusText}`);
  }

  return response.json();
}

export async function healthCheck() {
  const response = await fetch(`${API_BASE}/`);
  return response.json();
}

export async function fetchAdvisory(lat: number, lon: number) {
  const params = new URLSearchParams({
    lat: lat.toString(),
    lon: lon.toString(),
  });

  const response = await fetch(`${API_BASE}/advisory?${params}`);
  if (!response.ok) {
    throw new Error(`Advisory fetch failed: ${response.statusText}`);
  }

  return response.json();
}
