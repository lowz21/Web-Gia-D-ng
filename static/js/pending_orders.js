(function () {
  const STORAGE_KEY = "pending_order_refs";

  function readRefs() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list : [];
    } catch {
      return [];
    }
  }

  function writeRefs(refs) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(refs));
  }

  window.PendingOrders = {
    STORAGE_KEY,
    readRefs,
    writeRefs,

    rememberOrder(orderId, token) {
      if (!orderId) return;
      const refs = readRefs().filter((r) => String(r.id) !== String(orderId));
      refs.unshift({ id: Number(orderId), token: token || null });
      writeRefs(refs.slice(0, 20));
    },

    removeOrder(orderId) {
      writeRefs(readRefs().filter((r) => String(r.id) !== String(orderId)));
    },

    async fetchPending() {
      // Sử dụng API mới cho user đã đăng nhập
      const res = await fetch("/api/pending-orders", {
        method: "GET",
        credentials: "same-origin",
      });
      if (!res.ok) return { orders: [], count: 0 };
      const data = await res.json();
      return { orders: data.pending_orders || [], count: (data.pending_orders || []).length };
    },

    async pollStatus(orderId, token) {
      const q = token ? `?token=${encodeURIComponent(token)}` : "";
      const res = await fetch(`/api/orders/${orderId}/status${q}`, {
        credentials: "same-origin",
      });
      if (!res.ok) return null;
      return res.json();
    },

    formatCountdown(expiresAt) {
      if (!expiresAt) return "--:--";
      const end = new Date(expiresAt.includes("T") ? expiresAt : expiresAt.replace(" ", "T"));
      const diff = Math.max(0, Math.floor((end - Date.now()) / 1000));
      const m = Math.floor(diff / 60);
      const s = diff % 60;
      return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    },
  };

  function ensureBanner() {
    let bar = document.getElementById("pending-payment-banner");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "pending-payment-banner";
      bar.className = "pending-payment-banner hidden";
      bar.innerHTML =
        '<a href="/don-hang-cho-thanh-toan" class="pending-payment-banner-link">' +
        "Bạn có đơn hàng chưa hoàn tất thanh toán. Bấm vào đây để thanh toán ngay." +
        "</a>";
      const header = document.querySelector(".site-header");
      if (header) header.after(bar);
    }
    return bar;
  }

  async function refreshBanner() {
    const bar = ensureBanner();
    const data = await PendingOrders.fetchPending();
    if (data.count > 0) {
      bar.classList.remove("hidden");
    } else {
      bar.classList.add("hidden");
    }
    window.dispatchEvent(new CustomEvent("pending-orders-updated", { detail: data }));
    return data;
  }

  document.addEventListener("DOMContentLoaded", function () {
    refreshBanner();
    setInterval(refreshBanner, 30000);
  });

  window.refreshPendingPaymentBanner = refreshBanner;
})();
