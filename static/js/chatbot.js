document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('chatbot-toggle');
  const panel = document.getElementById('chatbot-panel');
  const input = document.getElementById('chatbot-input');
  const sendBtn = document.getElementById('chatbot-send');
  const messages = document.getElementById('chatbot-messages');

  if (!toggle) return;

  toggle.addEventListener('click', () => panel.classList.toggle('open'));

  // 1. Hàm thêm tin nhắn (hỗ trợ xuống dòng và link HTML)
  function addMessage(text, type, id = null) {
    const div = document.createElement('div');
    div.className = `chat-msg ${type}`;
    if (id) div.id = id;

    // Chuyển ký tự xuống dòng \n thành thẻ <br> để hiển thị đẹp mắt
    div.innerHTML = text.replace(/\n/g, '<br>');

    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  // 2. Hiển thị & Xóa trạng thái AI đang gõ
  function showLoading() {
    return addMessage('<i>Gia Dụng Pro đang suy nghĩ...</i>', 'bot loading', 'typing-indicator');
  }

  function removeLoading() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
  }

  // 3. Hàm gửi tin nhắn
  async function sendMessage() {
    const text = input.value.trim();
    if (!text || input.disabled) return;

    // Khóa input và hiển thị tin nhắn người dùng
    addMessage(text, 'user');
    input.value = '';
    input.disabled = true;
    sendBtn.disabled = true;

    // Hiển thị hiệu ứng chờ
    showLoading();

    try {
      const res = await fetch('/api/chatbot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });

      const data = await res.json();
      removeLoading();

      if (data && data.reply) {
        addMessage(data.reply, 'bot');
      } else {
        addMessage('Rất tiếc, hệ thống đang bận. Vui lòng thử lại sau!', 'bot');
      }
    } catch (error) {
      removeLoading();
      addMessage('Không thể kết nối chatbot. Vui lòng kiểm tra lại mạng!', 'bot');
    } finally {
      // Mở lại ô nhập tin nhắn sau khi phản hồi xong
      input.disabled = false;
      sendBtn.disabled = false;
      input.focus();
    }
  }

  sendBtn.addEventListener('click', sendMessage);
  input.addEventListener('keypress', (e) => { 
    if (e.key === 'Enter') sendMessage(); 
  });

  // Tin nhắn chào
  addMessage('Xin chào! Tôi là trợ lý Gia Dụng Pro. Bạn cần tư vấn sản phẩm hay kiểm tra đơn hàng nào?', 'bot');
});