┌──────────────────┐
                         │   INCOMING CALL   │
                         └────────┬─────────┘
                                  │
                                  ▼
                     ┌────────────────────────┐
                     │ Gujarati Welcome Menu  │
                     │                        │
                     │ Press 1 → Dr. Shaishav │
                     │ Press 2 → Dr. Jaydeep  │
                     │ Press 3 → Other Info   │
                     └───────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
             (1)                (2)                (3)
              │                  │                  │
              ▼                  ▼                  ▼
       Dr. Shaishav       Dr. Jaydeep       Other Information
              │                  │                  │
              └────────┬─────────┘                  │
                       │                            ▼
                       │                    Play existing Gujarati
                       │                    other-information audio
                       │                            │
                       │                            ▼
                       │                          Hangup
                       │
                       ▼
              CHECK TODAY'S AVAILABILITY
                       │
                ┌──────┴──────┐
                │             │
             AVAILABLE     NOT AVAILABLE
                │             │
                ▼             ▼
       Play today's slot    "આજે ડોક્ટર માટે
       / timing             કોઈ સ્લોટ ઉપલબ્ધ નથી"
                │             │
                ▼             ▼
       Press 1 → Booking     Press 2 → Main Menu
       Press 2 → Main Menu
                │
                ▼
        MOBILE NUMBER CAPTURE
                │
                ▼
       "તમારો 10 અંકનો મોબાઇલ
        નંબર દાખલ કરો અને # દબાવો"
                │
                ▼
         User enters 10 digits #
                │
                ▼
          VALIDATE NUMBER
                │
         ┌──────┴──────┐
         │             │
       INVALID        VALID
         │             │
         ▼             ▼
      Retry       Speak number
                       │
                       ▼
                Press 1 Confirm
                Press 2 Re-enter
                       │
                       ▼
                MOBILE CONFIRMED
                       │
                       ▼
                  NAME CAPTURE
                       │
                       ▼
              "કૃપા કરીને તમારું
               નામ જણાવો"
                       │
                       ▼
             Exotel Voice Stream
                       │
                       ▼
                  Sarvam STT
                   gu-IN
                       │
                       ▼
             Recognized Gujarati Name
                       │
                       ▼
          "તમારું નામ ______ છે.
           સાચું હોય તો 1 દબાવો.
           ફરીથી કહેવા માટે 2 દબાવો."
                       │
                ┌──────┴──────┐
                │             │
               (1)           (2)
                │             │
                ▼             └──────► Name Capture Retry
           NAME CONFIRMED
                │
                ▼
        FINAL CONFIRMATION
                │
                ▼
       "તમારું નામ ______ છે.
        તમારો મોબાઇલ નંબર ______ છે.
        ડોક્ટર ______ માટે આજનો સમય ______ છે.
        બુક કરવા માટે 1 દબાવો.
        મુખ્ય મેનુ માટે 2 દબાવો."
                │
          ┌─────┴─────┐
          │           │
         (1)         (2)
          │           │
          ▼           ▼
       BOOKING      MAIN MENU
          │
          ▼
       DB TRANSACTION
          │
          ├── Lock doctor/date
          ├── Verify availability
          ├── Create/upsert patient
          ├── Create appointment
          └── Generate appointment ID
          │
          ▼
     BOOKING SUCCESS
          │
          ▼
 "તમારી એપોઇન્ટમેન્ટ સફળતાપૂર્વક
  બુક થઈ ગઈ છે.
  તમારું નામ ______ છે.
  તમારો મોબાઇલ નંબર ______ છે.
  તમારો એપોઇન્ટમેન્ટ નંબર ______ છે.
  સમય ______ છે."
          │
          ▼
        HANGUP