/**
 * API Client Module for Backend Services.
 */
const API = {
  async getDoctors() {
    const res = await fetch('/api/doctors');
    return res.json();
  },

  async getAppointments(date = '', doctorId = '', search = '') {
    let url = `/api/appointments?date=${date}&doctor_id=${doctorId}&search=${encodeURIComponent(search)}`;
    const res = await fetch(url);
    return res.json();
  },

  async bookManualAppointment(data) {
    const res = await fetch('/api/appointments/manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return res.json();
  },

  async updateAppointmentStatus(id, status) {
    const res = await fetch(`/api/appointments/${id}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    });
    return res.json();
  },

  async getSchedules(doctorId, date) {
    const res = await fetch(`/api/schedules?doctor_id=${doctorId}&date=${date}`);
    return res.json();
  },

  async saveSlot(slotData) {
    const res = await fetch('/api/schedules/slot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(slotData)
    });
    return res.json();
  }
};
