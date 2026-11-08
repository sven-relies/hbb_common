# Home Assistant integraties

Verzameling van eigen Home Assistant custom integraties.

| Integratie | Map | Beschrijving |
|---|---|---|
| Kia + Zaptec Laden | [`custom_components/kia_zaptec`](custom_components/kia_zaptec) | Kia EV2 (Kia Connect) en Zaptec Go 2 uitlezen en bedienen, live laadvermogen, energie en kosten. [Documentatie](docs/kia_zaptec.md) |

## Installeren

Kopieer de map van de integratie die je wilt (bijv. `custom_components/kia_zaptec`) naar
`config/custom_components/` in je Home Assistant en herstart. Daarna toevoegen via
**Instellingen → Apparaten & diensten → Integratie toevoegen**.

Updaten: kopieer de map opnieuw en herstart.

> HACS installeert maar één integratie per repository, daarom gaat installeren hier via kopiëren.

## Ontwikkelen

```bash
pip install -r requirements_test.txt
pytest
```

Elke push draait via GitHub Actions de officiële Home Assistant-controle (hassfest) en de tests.

### Nieuwe integratie toevoegen
1. Maak `custom_components/<naam>/` met `manifest.json`, `__init__.py`, enz.
2. Zet de documentatie in `docs/<naam>.md` en voeg een regel toe aan de tabel hierboven.
3. Zet tests in `tests/<naam>/`.
