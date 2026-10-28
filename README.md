# Willhaben land search → OpenStreetMap prototype

This local Python prototype converts a **manually saved Willhaben search-results page** into:

- `listings.json` with title, displayed price, area, location and advertisement URL
- `willhaben_map.html`, an interactive OpenStreetMap map with clickable pins
- `geocode_cache.json`, so a location is not repeatedly sent to Nominatim

## Why it does not fetch the pasted URL itself

Willhaben's published `robots.txt` expressly forbids spiders, search robots and other automatic access unless permission is granted. Therefore this prototype does not send automated requests to Willhaben. You manually open the result page, then save the rendered HTML. This is also less fragile than trying to bypass anti-bot controls.

## Setup (Windows / PowerShell)

```powershell
cd path\to\willhaben_map_prototype
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Use

1. Open/refine the Willhaben result page normally.
2. Scroll through the loaded result list so all desired cards are present.
3. Press `Ctrl+S` and save as **Webpage, HTML only**. Example: `willhaben-results.html`.
4. Replace the placeholder email in `--user-agent` with a real contact address and run:

```powershell
python willhaben_map.py "C:\Users\David\Downloads\willhaben-results.html" `
  --user-agent "DavidWillhabenMapPrototype/0.1 (contact: your-email@example.com)"
```

5. Open `willhaben_map.html` in Edge.

## Accuracy limits

- Search cards often expose only postcode/town, not the parcel's exact coordinates. Pins can therefore represent the town centre, not the actual land parcel.
- The HTML parser is heuristic because site markup may change. Inspect `listings.json` before relying on the output.
- The public Nominatim server is suitable only for a small, personal prototype. This program uses one thread, waits more than one second between uncached requests, identifies itself with a User-Agent, and caches responses.
- The generated map loads OpenStreetMap tiles in the browser. Do not use it for offline bulk downloading or high-traffic production use.

## Troubleshooting

If zero listings are found:

- make sure the result page was fully loaded before saving;
- use **HTML only**, not a screenshot or PDF;
- inspect the HTML for links containing `/iad/immobilien/d/`;
- the selector may need updating if Willhaben changes its URL structure.

If a marker is missing, inspect `geocode_status` and `location` in `listings.json`. You can manually correct the location in JSON in a later version, or add exact coordinates obtained from an advertisement.

## Next sensible iteration

Add a small Streamlit UI and a browser extension/bookmarklet that extracts only visible listing cards from the page you opened, then posts the structured records to the local app. Later, enrich individual advertisements only after clarifying permission/terms and add typed fields such as `broker_commission`, `aufschliessung_status`, and an evidence snippet for every extracted claim.
