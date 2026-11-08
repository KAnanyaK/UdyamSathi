# Udyam Sathi demo walkthrough (3 minutes)

## 0:00–0:45 · Advisor voice note in Hindi

Open the chat in the Hindi language setting. Tap the microphone, then say: “मेरी किराना दुकान है, चार लोग काम करते हैं और एक जगह है। मुझे अच्छा इंटरनेट और बिलिंग चाहिए।” The browser speech recognition fills the message; the deterministic advisor answers in Hindi, gives three short reasons, and shows the monthly estimate returned by the pricing API. Play the reply aloud with the speaker control.

## 0:45–1:15 · Quote and add-ons

Open **Quote**. Point out the expected monthly total, the catalogue min–max range, setup fees, contract length, and install estimate. Toggle a primary-link dependent add-on such as failover; explain that the API recalculates the quote and blocks failover until a main link is included. Try a GSTIN-restricted add-on with the no-GSTIN salon persona to show the lock state.

## 1:15–2:15 · KYC, lookup, OCR, consent

Accept the quote to create an order and reserve the demo installation window. On KYC, review the four separate unchecked consent choices. Demonstrate the GSTIN or Udyam registry lookup using one of the IDs in the synthetic dataset. Upload one of the provided specimen images: its watermark identifies it as a non-valid synthetic sample and routes it for review. The API retains only the extracted metadata and validation result, then discards the image bytes. The registry lookup data and specimen IDs are synthetic.

## 2:15–2:45 · Tracker and partner console

Open **Track** to show the order ID and expected-by date. Use **Simulate next step** to advance the demo state machine. Open **Partner** and load the synthetic follow-up queue. Explain that partner records show stage, drop reason, and a sorted demo propensity estimate; KYC uploads and extracted IDs are not included.

## 2:45–3:00 · KPIs

Show the lead count, activated count, activation rate, and follow-up queue. All figures are derived from the included synthetic leads file. Close by noting the demo's data is fictional and Accel Business is a fictional operator.
