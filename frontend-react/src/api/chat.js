import api from './axiosInstance';

export async function createConversation(title = 'New Conversation') {
  const res = await api.post('/chats', { title });
  return res.data;
}

export async function listConversations() {
  const res = await api.get('/chats');
  return res.data; // array of ConversationOut
}

export async function getConversation(chatId) {
  const res = await api.get(`/chats/${chatId}`);
  return res.data; // ConversationDetailOut
}

export async function deleteConversation(chatId) {
  await api.delete(`/chats/${chatId}`);
}

export async function renameConversation(chatId, title) {
  const res = await api.patch(`/chats/${chatId}`, { title });
  return res.data;
}

export async function sendMessage(chatId, { content, attachment_id = null }) {
  const res = await api.post(`/chats/${chatId}/messages`, {
    content,
    attachment_id
  });
  return res.data; // { message, veritas_result, conversation_title }
}

export async function uploadAttachment(chatId, file) {
  const formData = new FormData();
  formData.append('file', file);
  
  const res = await api.post(`/chats/${chatId}/attachments`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
  return res.data; // AttachmentOut
}

export async function getVeritasResult(chatId, messageId) {
  const res = await api.get(`/chats/${chatId}/messages/${messageId}/veritas`);
  return res.data;
}
