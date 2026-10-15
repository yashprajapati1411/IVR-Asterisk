/**
 * Receptionist Dashboard Application Logic.
 * Trinay Orthopedic Hospital — Receptionist Portal
 */
document.addEventListener('alpine:init', () => {
  Alpine.data('dashboard', () => ({
    activeTab: 'appointments',
    
    // Filters & States
    doctors: [],
    selectedDoctorId: '',
    selectedDate: new Date().toLocaleDateString('en-CA'),
    selectedShift: '', // '' for All, 'MORNING', 'EVENING'
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
    stats: { total: 0, ivr: 0, manual: 0, confirmed: 0, morning: 0, evening: 0 },

    get filteredAppointments() {
      if (!this.selectedShift) return this.appointments;
      return this.appointments.filter(a => (a.shift || 'MORNING') === this.selectedShift);
    },
    
    // Manual Booking Modal
    showBookingModal: false,
    manualBookShift: 'ALL',
    manualBook: {
      doctor_id: 1,
      patient_name_gu: '',
      mobile_number: '',
      target_date: new Date().toISOString().split('T')[0],
      slot_time_gu: ''
    },
    availableSlotsForManual: [],

    get filteredAvailableSlotsForManual() {
      if (this.manualBookShift === 'ALL') return this.availableSlotsForManual;
      return this.availableSlotsForManual.filter(s => (s.shift || 'MORNING') === this.manualBookShift);
    },

    // Schedule Manager State
    scheduleDate: new Date().toISOString().split('T')[0],
    scheduleDoctorId: 1,
    scheduleShift: 'ALL', // 'ALL', 'MORNING', 'EVENING'
    schedules: [],
    loadingSchedules: false,

    get filteredSchedules() {
      if (this.scheduleShift === 'ALL') return this.schedules;
      return this.schedules.filter(s => (s.shift || 'MORNING') === this.scheduleShift);
    },

    get morningSlots() {
      return this.schedules.filter(s => (s.shift || 'MORNING') === 'MORNING');
    },

    get eveningSlots() {
      return this.schedules.filter(s => (s.shift || 'MORNING') === 'EVENING');
    },

    get morningCapacity() {
      return this.morningSlots.reduce((sum, s) => sum + (s.max_slots || 0), 0);
    },

    get morningBooked() {
      return this.morningSlots.reduce((sum, s) => sum + (s.booked_count || 0), 0);
    },

    get eveningCapacity() {
      return this.eveningSlots.reduce((sum, s) => sum + (s.max_slots || 0), 0);
    },

    get eveningBooked() {
      return this.eveningSlots.reduce((sum, s) => sum + (s.booked_count || 0), 0);
    },

    // Custom 1-Hour Slot Modal
    showSlotModal: false,
    slotModalError: '',
    customSlot: {
      slot_id: null,
      doctor_id: 1,
      schedule_date: new Date().toISOString().split('T')[0],
      shift: 'MORNING',
      start_time: '10:00',
      end_time: '11:00',
      slot_time_gu: 'સવારે 10:00 થી 11:00',
      slot_time_en: '10:00 AM to 11:00 AM',
      max_slots: 5,
      is_active: 1
    },

    morningPresets: [
      { start: '10:00', end: '11:00', gu: 'સવારે 10:00 થી 11:00', en: '10:00 AM to 11:00 AM' },
      { start: '11:00', end: '12:00', gu: 'સવારે 11:00 થી 12:00', en: '11:00 AM to 12:00 PM' },
      { start: '12:00', end: '13:00', gu: 'બપોરે 12:00 થી 1:00', en: '12:00 PM to 1:00 PM' },
      { start: '13:00', end: '14:00', gu: 'બપોરે 1:00 થી 2:00', en: '1:00 PM to 2:00 PM' },
      { start: '14:00', end: '15:00', gu: 'બપોરે 2:00 થી 3:00', en: '2:00 PM to 3:00 PM' },
      { start: '15:00', end: '16:00', gu: 'બપોરે 3:00 થી 4:00', en: '3:00 PM to 4:00 PM' }
    ],

    eveningPresets: [
      { start: '16:00', end: '17:00', gu: 'સાંજે 4:00 થી 5:00', en: '4:00 PM to 5:00 PM' },
      { start: '17:00', end: '18:00', gu: 'સાંજે 5:00 થી 6:00', en: '5:00 PM to 6:00 PM' },
      { start: '18:00', end: '19:00', gu: 'સાંજે 6:00 થી 7:00', en: '6:00 PM to 7:00 PM' },
      { start: '19:00', end: '20:00', gu: 'સાંજે 7:00 થી 8:00', en: '7:00 PM to 8:00 PM' },
      { start: '20:00', end: '21:00', gu: 'રાત્રે 8:00 થી 9:00', en: '8:00 PM to 9:00 PM' }
    ],

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
        if (this.isAuthenticated && this.activeTab === 'appointments' && !this.showBookingModal && !this.showSlotModal) {
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
      this.stats.morning = this.appointments.filter(a => (a.shift || 'MORNING') === 'MORNING').length;
      this.stats.evening = this.appointments.filter(a => a.shift === 'EVENING').length;
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
          shift: slot.shift || 'MORNING',
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
          shift: slot.shift || 'MORNING',
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

    async deleteSlot(slot) {
      if (!confirm(`શું તમે આ સ્લોટ (${slot.slot_time_gu}) ડિલીટ કરવા માંગો છો?`)) return;
      try {
        const res = await API.deleteSlot(slot.id);
        if (res.success) {
          await this.fetchSchedules();
        } else {
          alert(res.detail || res.error || 'સ્લોટ ડિલીટ કરી શકાયો નથી.');
        }
      } catch (err) {
        alert('ભૂલ: ' + err.message);
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

    setShift(shift) {
      this.customSlot.shift = shift;
      this.slotModalError = '';
      if (shift === 'MORNING') {
        this.applyPreset(this.morningPresets[0]);
      } else {
        this.applyPreset(this.eveningPresets[0]);
      }
    },

    applyPreset(preset) {
      this.customSlot.start_time = preset.start;
      this.customSlot.end_time = preset.end;
      this.customSlot.slot_time_gu = preset.gu;
      this.customSlot.slot_time_en = preset.en;
      this.slotModalError = '';
    },

    openCustomSlotModal(defaultShift = null) {
      const shift = defaultShift || (this.scheduleShift === 'EVENING' ? 'EVENING' : 'MORNING');
      this.customSlot = {
        slot_id: null,
        doctor_id: this.scheduleDoctorId,
        schedule_date: this.scheduleDate,
        shift: shift,
        start_time: shift === 'MORNING' ? '10:00' : '17:00',
        end_time: shift === 'MORNING' ? '11:00' : '18:00',
        slot_time_gu: shift === 'MORNING' ? 'સવારે 10:00 થી 11:00' : 'સાંજે 5:00 થી 6:00',
        slot_time_en: shift === 'MORNING' ? '10:00 AM to 11:00 AM' : '5:00 PM to 6:00 PM',
        max_slots: 5,
        is_active: 1
      };
      this.slotModalError = '';
      this.showSlotModal = true;
    },

    checkClientSideConflict() {
      const start = this.customSlot.start_time;
      const end = this.customSlot.end_time;
      for (const s of this.schedules) {
        if (this.customSlot.slot_id && s.id === this.customSlot.slot_id) continue;
        if (start < s.end_time && end > s.start_time) {
          const shiftLabel = s.shift === 'MORNING' ? 'સવારના (Morning)' : 'સાંજના (Evening)';
          return `આ સમય સ્લોટ પહેલેથી ${shiftLabel} સ્લોટમાં શેડ્યૂલ કરેલ સમય (${s.slot_time_gu}) સાથે ઓવરલેપ થાય છે!`;
        }
      }
      return null;
    },

    async submitCustomSlot() {
      this.slotModalError = '';
      const conflictMsg = this.checkClientSideConflict();
      if (conflictMsg) {
        this.slotModalError = conflictMsg;
        return;
      }

      try {
        const res = await API.saveSlot(this.customSlot);
        if (res.success) {
          this.showSlotModal = false;
          await this.fetchSchedules();
        } else {
          this.slotModalError = res.detail || res.error || 'સ્લોટ સાચવવામાં નિષ્ફળતા મળી.';
        }
      } catch (err) {
        this.slotModalError = 'ભૂલ: ' + err.message;
      }
    }
  }));
});
