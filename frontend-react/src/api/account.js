import api from './axiosInstance';

export async function getAccount() {
  const res = await api.get('/account/me');
  return res.data;
}

export async function updateAccount({ name }) {
  const res = await api.patch('/account/me', { name });
  return res.data;
}
