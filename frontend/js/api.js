/**
 * API Client Module for Backend Services with Authentication Support.
 */
const API = {
  TOKEN_KEY: 'trinay_auth_token',

  getToken() {
    return localStorage.getItem(this.TOKEN_KEY) || '';
  },

  setToken(token) {
    if (token) {
      localStorage.setItem(this.TOKEN_KEY, token);
    } else {
      localStorage.removeItem(this.TOKEN_KEY);
    }
  },

  async login(username, password) {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (res.ok && data.token) {
      this.setToken(data.token);
    }
    return { status: res.status, ...data };
  },

  logout() {
    this.setToken(null);
  },

  async fetchWithAuth(url, options = {}) {
    const headers = options.headers || {};
    const token = this.getToken();
    if (token) {
      headers['X-Auth-Token'] = token;
      headers['Authorization'] = `Bearer ${token}`;
    }
    const response = await fetch(url, { ...options, headers });
    if (response.status === 401) {
      this.logout();
      window.dispatchEvent(new CustomEvent('auth-unauthorized'));
    }
    return response;
  },

  async getDoctors() {
    const res = await this.fetchWithAuth('/api/doctors');
    return res.json();
  },

  async getAppointments(date = '', doctorId = '', search = '') {
    const params = [];
    if (date && String(date).trim()) params.push(`date=${encodeURIComponent(String(date).trim())}`);
    if (doctorId) params.push(`doctor_id=${encodeURIComponent(doctorId)}`);
    if (search && String(search).trim()) params.push(`search=${encodeURIComponent(String(search).trim())}`);
    let url = '/api/appointments' + (params.length ? `?${params.join('&')}` : '');
    const res = await this.fetchWithAuth(url);
    return res.json();
  },

  async bookManualAppointment(data) {
    const res = await this.fetchWithAuth('/api/appointments/manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return res.json();
  },

  async updateAppointmentStatus(id, status) {
    const res = await this.fetchWithAuth(`/api/appointments/${id}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    });
    return res.json();
  },

  async getSchedules(doctorId, date) {
    const res = await this.fetchWithAuth(`/api/schedules?doctor_id=${doctorId}&date=${date}`);
    return res.json();
  },

  async saveSlot(slotData) {
    const res = await this.fetchWithAuth('/api/schedules/slot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(slotData)
    });
    return res.json();
  }
};
