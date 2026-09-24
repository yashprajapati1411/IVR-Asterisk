/**
 * Receptionist Dashboard Application Logic.
 */
document.addEventListener('alpine:init', () => {
  Alpine.data('dashboard', () => ({
    activeTab: 'appointments',
    
    // Filters & States
    doctors: [],
    selectedDoctorId: '',
    selectedDate: new Date().toISOString().split('T')[0],
    searchQuery: '',

    get isTodaySelected() {
      return this.selectedDate === new Date().toISOString().split('T')[0];
    },

    setTodayDate() {
      this.selectedDate = new Date().toISOString().split('T')[0];
      this.fetchAppointments();
    },
    
    // Appointments Data
    appointments: [],
    loadingAppts: false,
    stats: { total: 0, ivr: 0, manual: 0, confirmed: 0 },
    
    // Manual Booking Modal
    showBookingModal: false,
    manualBook: {
      doctor_id: 1,
      patient_name_gu: '',
      mobile_number: '',
      target_date: new Date().toISOString().split('T')[0],
      slot_time_gu: ''
    },
    availableSlotsForManual: [],

    // Schedule Manager State
    scheduleDate: new Date().toISOString().split('T')[0],
    scheduleDoctorId: 1,
    schedules: [],
    loadingSchedules: false,

    // Custom Slot Modal
    showSlotModal: false,
    customSlot: {
      slot_id: null,
      doctor_id: 1,
      schedule_date: new Date().toISOString().split('T')[0],
      start_time: '14:00',
      end_time: '15:00',
      slot_time_gu: 'બપોરે 2:00 થી 3:00',
      slot_time_en: '2:00 PM to 3:00 PM',
      max_slots: 8,
      is_active: 1
    },

    async init() {
      await this.loadDoctors();
      await this.fetchAppointments();
      await this.fetchSchedules();

      // Auto-refresh appointments every 5 seconds
      setInterval(() => {
        if (this.activeTab === 'appointments' && !this.showBookingModal) {
          this.fetchAppointments(true);
        }
      }, 5000);
    },

    async loadDoctors() {
      try {
        const res = await API.getDoctors();
        if (res.success) {
          this.doctors = res.doctors;
          if (this.doctors.length > 0) {
            this.manualBook.doctor_id = this.doctors[0].id;
            this.scheduleDoctorId = this.doctors[0].id;
          }
        }
      } catch (err) {
        console.error('Failed to load doctors:', err);
      }
    },

    async fetchAppointments(silent = false) {
      if (!silent) this.loadingAppts = true;
      try {
        const res = await API.getAppointments(this.selectedDate, this.selectedDoctorId, this.searchQuery);
        if (res.success) {
          this.appointments = res.appointments;
          this.calculateStats();
        }
      } catch (err) {
        console.error('Failed to fetch appointments:', err);
      } finally {
        if (!silent) this.loadingAppts = false;
      }
    },

    calculateStats() {
      this.stats.total = this.appointments.length;
      this.stats.ivr = this.appointments.filter(a => a.source === 'IVR').length;
      this.stats.manual = this.appointments.filter(a => a.source === 'MANUAL').length;
      this.stats.confirmed = this.appointments.filter(a => a.status === 'CONFIRMED').length;
    },

    async updateStatus(apptId, newStatus) {
      try {
        const res = await API.updateAppointmentStatus(apptId, newStatus);
        if (res.success) {
          await this.fetchAppointments(true);
          if (this.activeTab === 'schedules') await this.fetchSchedules();
        }
      } catch (err) {
        alert('Failed to update status: ' + err.message);
      }
    },

    async openManualBookingModal() {
      this.manualBook.target_date = this.selectedDate || new Date().toISOString().split('T')[0];
      await this.loadSlotsForManualBooking();
      this.showBookingModal = true;
    },

    async loadSlotsForManualBooking() {
      try {
        const res = await API.getSchedules(this.manualBook.doctor_id, this.manualBook.target_date);
        if (res.success) {
          this.availableSlotsForManual = res.schedules;
          if (this.availableSlotsForManual.length > 0) {
            this.manualBook.slot_time_gu = this.availableSlotsForManual[0].slot_time_gu;
          }
        }
      } catch (err) {
        console.error('Failed to load slots for manual booking:', err);
      }
    },

    async submitManualBooking() {
      if (!this.manualBook.patient_name_gu || !this.manualBook.mobile_number) {
        alert('કૃપા કરીને નામ અને મોબાઇલ નંબર દાખલ કરો.');
        return;
      }
      try {
        const res = await API.bookManualAppointment(this.manualBook);
        if (res.success) {
          alert(`એપોઇન્ટમેન્ટ સફળતાપૂર્વક બુક થઈ! ટોકન નંબર: ${res.appointment_code}`);
          this.showBookingModal = false;
          this.manualBook.patient_name_gu = '';
          this.manualBook.mobile_number = '';
          await this.fetchAppointments();
          await this.fetchSchedules();
        } else {
          alert('બુકિંગ નિષ્ફળ: ' + (res.detail || res.error));
        }
      } catch (err) {
        alert('એરર: ' + err.message);
      }
    },

    // Schedule Management Logic
    async fetchSchedules() {
      this.loadingSchedules = true;
      try {
        const res = await API.getSchedules(this.scheduleDoctorId, this.scheduleDate);
        if (res.success) {
          this.schedules = res.schedules;
        }
      } catch (err) {
        console.error('Failed to fetch schedules:', err);
      } finally {
        this.loadingSchedules = false;
      }
    },

    async updateSlotCapacity(slot, delta) {
      const newMax = Math.max(1, slot.max_slots + delta);
      try {
        const res = await API.saveSlot({
          slot_id: slot.id,
          doctor_id: slot.doctor_id,
          schedule_date: this.scheduleDate,
          start_time: slot.start_time,
          end_time: slot.end_time,
          slot_time_gu: slot.slot_time_gu,
          slot_time_en: slot.slot_time_en,
          max_slots: newMax,
          is_active: slot.is_active
        });
        if (res.success) {
          await this.fetchSchedules();
        }
      } catch (err) {
        alert('Failed to update capacity: ' + err.message);
      }
    },

    async toggleSlotActive(slot) {
      const newActive = slot.is_active ? 0 : 1;
      try {
        const res = await API.saveSlot({
          slot_id: slot.id,
          doctor_id: slot.doctor_id,
          schedule_date: this.scheduleDate,
          start_time: slot.start_time,
          end_time: slot.end_time,
          slot_time_gu: slot.slot_time_gu,
          slot_time_en: slot.slot_time_en,
          max_slots: slot.max_slots,
          is_active: newActive
        });
        if (res.success) {
          await this.fetchSchedules();
        }
      } catch (err) {
        alert('Failed to toggle slot: ' + err.message);
      }
    },

    openCustomSlotModal() {
      this.customSlot = {
        slot_id: null,
        doctor_id: this.scheduleDoctorId,
        schedule_date: this.scheduleDate,
        start_time: '14:00',
        end_time: '15:00',
        slot_time_gu: 'બપોરે 2:00 થી 3:00',
        slot_time_en: '2:00 PM to 3:00 PM',
        max_slots: 8,
        is_active: 1
      };
      this.showSlotModal = true;
    },

    async submitCustomSlot() {
      try {
        const res = await API.saveSlot(this.customSlot);
        if (res.success) {
          this.showSlotModal = false;
          await this.fetchSchedules();
        }
      } catch (err) {
        alert('Failed to add custom slot: ' + err.message);
      }
    }
  }));
});
