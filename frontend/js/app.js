/**
 * Receptionist Dashboard Application Logic.
 */
document.addEventListener('alpine:init', () => {
  Alpine.data('dashboard', () => ({
    activeTab: 'appointments',
    
    // Filters & States
    doctors: [],
    selectedDoctorId: '',
    selectedDate: new Date().toLocaleDateString('en-CA'),
    searchQuery: '',

    get isTodaySelected() {
      return this.selectedDate === new Date().toLocaleDateString('en-CA');
    },

    setTodayDate() {
      this.selectedDate = new Date().toLocaleDateString('en-CA');
      this.fetchAppointments();
    },

    setAllDates() {
      this.selectedDate = '';
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

    // Authentication State
    isAuthenticated: !!API.getToken(),
    loginForm: {
      username: 'trinay@2026',
      password: '',
      error: '',
      loading: false
    },

    async init() {
      // Listen for unauthorized 401 events from API
      window.addEventListener('auth-unauthorized', () => {
        this.isAuthenticated = false;
        this.loginForm.password = '';
        this.loginForm.error = 'સત્ર સમાપ્ત થઈ ગયું છે. કૃપા કરીને ફરી લૉગિન કરો. (Session expired. Please log in again.)';
      });

      if (this.isAuthenticated) {
        await this.loadInitialData();
      }

      // Auto-refresh appointments every 5 seconds (only when authenticated)
      setInterval(() => {
        if (this.isAuthenticated && this.activeTab === 'appointments' && !this.showBookingModal) {
          this.fetchAppointments(true);
        }
      }, 5000);
    },

    async loadInitialData() {
      await this.loadDoctors();
      await this.fetchAppointments();
      await this.fetchSchedules();
    },

    async submitLogin() {
      this.loginForm.error = '';
      if (!this.loginForm.username.trim() || !this.loginForm.password.trim()) {
        this.loginForm.error = 'કૃપા કરીને યુઝરનેમ અને પાસવર્ડ દાખલ કરો.';
        return;
      }
      this.loginForm.loading = true;
      try {
        const res = await API.login(this.loginForm.username, this.loginForm.password);
        if (res.success && res.token) {
          this.isAuthenticated = true;
          this.loginForm.password = '';
          this.loginForm.error = '';
          await this.loadInitialData();
        } else {
          this.loginForm.error = res.detail || 'ખોટો યુઝરનેમ અથવા પાસવર્ડ (Invalid username or password)';
        }
      } catch (err) {
        console.error('Login error:', err);
        this.loginForm.error = 'સર્વર સાથે કનેક્ટ થવામાં ભૂલ થઈ. (Server connection failed)';
      } finally {
        this.loginForm.loading = false;
      }
    },

    logout() {
      API.logout();
      this.isAuthenticated = false;
      this.appointments = [];
      this.doctors = [];
      this.schedules = [];
      this.loginForm.password = '';
      this.loginForm.error = '';
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

    formatTimePart(timeStr, isEnd = false) {
      if (!timeStr) return null;
      let clean = timeStr.trim();
      let parts = clean.split(':');
      if (parts.length < 1) return null;
      let h = parseInt(parts[0], 10);
      let m = parts[1] ? parts[1].padStart(2, '0') : '00';
      if (isNaN(h)) return null;

      if (isEnd && (h === 0 || h === 24) && parseInt(m, 10) === 0) {
        return { hour12: 12, display: `12:${m}`, ampm: 'AM', periodGu: 'રાત્રે' };
      }

      let ampm = h >= 12 ? 'PM' : 'AM';
      let hour12 = h % 12 || 12;
      let periodGu = 'સવારે';
      if (h >= 12 && h < 16) periodGu = 'બપોરે';
      else if (h >= 16 && h < 20) periodGu = 'સાંજે';
      else if (h >= 20 || h === 0) periodGu = 'રાત્રે';

      return { hour12, display: `${hour12}:${m}`, ampm, periodGu };
    },

    updateCustomSlotLabels() {
      const s = this.formatTimePart(this.customSlot.start_time, false);
      const e = this.formatTimePart(this.customSlot.end_time, true);
      if (s && e) {
        this.customSlot.slot_time_gu = `${s.periodGu} ${s.display} થી ${e.display}`;
        this.customSlot.slot_time_en = `${s.display} ${s.ampm} to ${e.display} ${e.ampm}`;
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
      this.updateCustomSlotLabels();
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
