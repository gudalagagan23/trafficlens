# Privacy note

TrafficLens is built so it can work without knowing who anyone is.

**What the tracker records (patterns only)**
- how long a visitor stayed on a page
- how many mouse movements and touches, and how straight the mouse path was
- number of clicks and bursts of angry clicks
- how far they scrolled
- how many times a form was submitted, and the time spent in it
- the traffic source, the device type and the browser family

**What it never records**
- anything typed (no keystrokes, no input values, no passwords, no card numbers)
- names, emails, IP addresses or exact locations
- anything that links a visit to a real person (the visit id is random and lasts one tab session)

**Before using it on a real site**
- Add a clear notice that behaviour patterns are measured.
- Check the privacy rules that apply to you (for example GDPR in Europe, DPDP in India).
- Keep the data only as long as you need it.

The collector (tracker/collector.py) drops any field it does not know, so extra data cannot slip in by accident.
