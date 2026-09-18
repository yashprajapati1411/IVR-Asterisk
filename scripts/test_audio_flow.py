"""
Windows Native Audio IVR Simulator.
Plays the actual Asterisk Gujarati .wav files through your Windows speakers
so you can hear exactly what the caller will hear!
"""
import os
import sys
import time
import winsound

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.tts_service import TTSService
from services.db_service import DatabaseService

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sounds", "gu")

def play_audio(filename):
    """Plays WAV file natively on Windows."""
    if not filename.endswith(".wav"):
        filename += ".wav"
    path = os.path.join(PROMPTS_DIR, filename)
    if not os.path.exists(path):
        # Could be a dynamic TTS cache file
        path = filename
    if os.path.exists(path):
        print(f"🔊 Playing Audio...")
        winsound.PlaySound(path, winsound.SND_FILENAME)
    else:
        print(f"[Audio file {path} not found]")

def get_dtmf(prompt):
    try:
        return input(f"\n📱 {prompt} ")
    except:
        return ""

def main():
    print("="*60)
    print("📞 INCOMING CALL ANSWERED")
    print("="*60)
    
    db = DatabaseService()
    tts = TTSService()
    
    # WELCOME
    play_audio("welcome_menu")
    dtmf = get_dtmf("Press 1 for Dr. Shaishav, 2 for Dr. Jaydeep, 3 for Other Info: ")
    
    if dtmf == "3":
        play_audio("other_info")
        print("\n📴 Call Hung Up")
        return
        
    doc_id = int(dtmf) if dtmf in ["1", "2"] else 1
    doc_name = "ડૉક્ટર શૈશવ" if doc_id == 1 else "ડૉક્ટર જયદીપ"
    
    # AVAILABILITY
    avail = db.check_availability(doc_id)
    if not avail.get("available"):
        play_audio("no_slots_today")
        print("\n📴 Call Hung Up")
        return
        
    slot_time = avail["slot_time_gu"]
    slot_text = f"{doc_name} માટે આજનો સમય {slot_time} છે. બુક કરવા માટે 1 દબાવો. મુખ્ય મેનુ માટે 2 દબાવો."
    slot_audio = tts.synthesize_gujarati(slot_text)
    play_audio(slot_audio)
    
    dtmf = get_dtmf("Press 1 to Book, 2 for Main Menu: ")
    if dtmf != "1":
        print("\n📴 Call Hung Up")
        return
        
    # MOBILE CAPTURE
    play_audio("enter_mobile")
    mobile = get_dtmf("Enter your 10-digit mobile number: ").replace("#", "")
    
    confirm_text = f"તમારો મોબાઇલ નંબર {', '.join(mobile)} છે. સાચું હોય તો 1 દબાવો. ફરીથી દાખલ કરવા માટે 2 દબાવો."
    mobile_audio = tts.synthesize_gujarati(confirm_text)
    play_audio(mobile_audio)
    get_dtmf("Press 1 to Confirm: ")
    
    # NAME CAPTURE
    play_audio("speak_name")
    print("🔴 [RECORDING BEEP]...")
    name = get_dtmf("(Simulate STT) Type your name in Gujarati or English: ")
    if not name: name = "ભાવેશભાઈ પટેલ"
    
    name_confirm_text = f"તમારું નામ {name} છે. સાચું હોય તો 1 દબાવો. ફરીથી કહેવા માટે 2 દબાવો."
    name_audio = tts.synthesize_gujarati(name_confirm_text)
    play_audio(name_audio)
    get_dtmf("Press 1 to Confirm: ")
    
    # FINAL CONFIRMATION
    final_text = f"તમારું નામ {name} છે. તમારો મોબાઇલ નંબર {', '.join(mobile)} છે. {doc_name} માટે આજનો સમય {slot_time} છે. બુક કરવા માટે 1 દબાવો."
    final_audio = tts.synthesize_gujarati(final_text)
    play_audio(final_audio)
    get_dtmf("Press 1 to Book: ")
    
    # DB TRANSACTION
    res = db.book_appointment(doc_id, mobile, name)
    
    # SUCCESS
    success_text = f"તમારી એપોઇન્ટમેન્ટ સફળતાપૂર્વક બુક થઈ ગઈ છે. તમારો એપોઇન્ટમેન્ટ નંબર {res['appointment_code']} છે. આભાર."
    success_audio = tts.synthesize_gujarati(success_text)
    play_audio(success_audio)
    
    print(f"\n🎉 APPOINTMENT CREATED: {res['appointment_code']}")
    print("\n📴 Call Hung Up")

if __name__ == "__main__":
    main()
