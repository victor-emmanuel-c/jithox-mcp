# Dogfood-voorbeeld 2026-09: een van onze eigen facturen door de live Jithox-poort

Kaart t_8109c72a (ROUTE D). Machineleesbare versie: `DOGFOOD_VOORBEELD_2026-09.json` (zelfde call, volledig antwoord).

De factuur (echt, ontvangen door Jithox op 2026-09-15)
------------------------------------------------------
- Leverancier: Shopify International Limited (Ierland), maandfactuur voor het Shopify-abonnement, als pdf-bijlage.
- Betaalwijze volgens de mail: PayPal. Er staat geen IBAN op de factuur.
- Btw: 0 %, verlegd ("As recipient you are liable to account for reverse charge VAT").
- Btw-nummer van de leverancier op de factuur: IE3347697KH.
- Afzender: DKIM pass, SPF pass, DMARC pass (beleid reject).
- Weggelaten: mailtekst, adressen, factuurnummer en bedrag.

De exacte live call (2026-09-24 08:47:16 UTC)
---------------------------------------------
```
python jx.py check_vat_list '{"rows":[{"reference":"Shopify Billing","vatId":"IE3347697KH"}],"requesterVatId":"BE1039898594"}'
```
jx.py is onze interne client. Hij stuurt dit als JSON-RPC `tools/call` naar `https://jithox.com/api/mcp` en markeert
elke call als eigen verkeer, zodat die niet als externe agent telt.

Zonder jx.py: POST deze body naar `https://jithox.com/api/mcp`, met `Authorization: Bearer <token>`,
`Content-Type: application/json` en `Accept: application/json, text/event-stream`:
```
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"check_vat_list","arguments":{"rows":[{"reference":"Shopify Billing","vatId":"IE3347697KH"}],"requesterVatId":"BE1039898594"}}}
```
De Commissie registreert de raadpleging op het requesterVatId dat je meestuurt (BE1039898594 is ons eigen btw-nummer).

Het echte antwoord (ingekort; het volledige antwoord staat in de .json)
-----------------------------------------------------------------------
```
register: valid
registeredName: SHOPIFY INTERNATIONAL LIMITED
consultationNumber: WAPIAAAAaDSmQEaU   (consultatienummer van de Europese Commissie)
consultationAt: 2026-09-24T08:47:17.951Z
billing: 1 credit (EUR 0,01), charged: true
```

Zelf narekenen
--------------
- Het EU-register: `https://ec.europa.eu/taxation_customs/vies/rest-api/ms/IE/vat/3347697KH`. Op 2026-09-24 08:06 UTC
  gaf dat `isValid: true`, naam SHOPIFY INTERNATIONAL LIMITED.
- Dezelfde call nog eens geeft `valid` met een nieuw consultatienummer. Het nummer geldt per raadpleging.

Waar de call terechtkwam (productie, read-only gemeten)
-------------------------------------------------------
- Funnel: `traffic = own_probe`, `tool_call_accepted` om 08:47:18 UTC.
- Tegoed: 1 credit, afgeschreven van de werkruimte met tegoedbron `internal_dogfood` (08:47:17 UTC).
- Deze call telt niet als externe agent en niet als omzet.

Wat dit NIET bewijst
--------------------
- Het bewijst niet dat de factuur echt of juist is. Het bewijst alleen dat het btw-nummer van de leverancier op
  dat moment in VIES stond, onder die naam.
- Het bewijst niets over de betaalrekening: er stond geen IBAN op de factuur, dus check_payment_change had niets te
  controleren.
- Het bewijst niet dat de factuur de fiscale regels volgt. Op deze factuur staat geen btw-nummer van de koper, terwijl
  een verlegde factuur dat wel moet hebben (Richtlijn 2006/112/EG art. 226, punt 4). Toen we dezelfde factuur
  handmatig in review_invoice invoerden, gaf dat onterecht `readyToSend: true`. Dat is een vals allow op de Peppol-regels
  BR-AE-02 en BR-AE-10 (allebei fatal). De fix staat op kaart t_d1260df8.
- Het bewijst niet dat een externe agent Jithox gebruikt. Wij hebben deze call zelf gedaan.
- Het bewijst niet dat de hele mailbox gecontroleerd is. Van de 13 kandidaten in 30 dagen had er maar 1 een IBAN of een
  EU-btw-nummer waarop de poort iets kan doen.
