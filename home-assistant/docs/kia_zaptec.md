# Kia + Zaptec Laden – Home Assistant integratie

Custom integratie die je **Kia EV2** (via Kia Connect) en je **Zaptec Go 2** (via de Zaptec cloud-API)
uitleest en ze combineert. Zo zie je live hoeveel de laadpaal levert en hoeveel de auto nog kan/moet laden.

## Wat je krijgt

**Zaptec Go 2** (standaard elke 15 s bijgewerkt)
| Entiteit | Betekenis |
|---|---|
| Laadvermogen | Wat de paal *nu* aan de auto levert (W) |
| Beschikbaar vermogen voor auto | Aangeboden laadstroom × spanning van de actieve fases (W): het maximum dat de auto nu zou kunnen trekken |
| Aangeboden laadstroom / Maximale stroom | A |
| Energie deze sessie | kWh geladen in de huidige sessie |
| Stroom L1–L3, Spanning L1–L3 | Per fase |
| Status laadpaal | Niet aangesloten / Wacht op auto / Aan het laden / Klaar |
| Totaal geladen energie | Meterstand van de laadpaal (kWh, alleen oplopend), voor het Energie-dashboard |
| Kosten deze sessie / Totale laadkosten | Geladen kWh × stroomprijs (vast of via een prijssensor) |

**Kia EV2** (standaard elke 5 min uit de Kia-cloud)
| Entiteit | Betekenis |
|---|---|
| Accu | Laadtoestand (%) |
| Actieradius | km |
| Tijd tot laadlimiet (auto) | Schatting van de auto zelf |
| Laadvermogen (auto) | Wat de auto rapporteert (kW, als de auto dit doorgeeft) |
| Aan het laden / Stekker aangesloten | binaire sensoren |
| Accugezondheid, Laatst bijgewerkt | diagnostiek |

**Gecombineerd**
| Entiteit | Berekening |
|---|---|
| Energie tot laadlimiet | (laadlimiet − accu%) × accucapaciteit → **hoeveel de auto nog kan laden** (kWh) |
| Energie tot 100% | (100 − accu%) × accucapaciteit |
| Tijd tot laadlimiet (live) | energie tot laadlimiet ÷ live Zaptec-vermogen (laadverliezen van ~5–10% niet meegerekend) |

**Bediening**
| Entiteit | Wat het doet |
|---|---|
| Laden toegestaan (Zaptec, schakelaar) | Uit = laden pauzeren, aan = hervatten. Werkt alleen als er een auto is aangesloten |
| Maximale laadstroom (Zaptec, schuif 6–32 A) | Hoeveel stroom de paal maximaal aan de auto geeft (begrensd door de installatie) |
| Laden (auto, schakelaar) | Laden starten/stoppen via Kia Connect |
| Laadlimiet AC / DC (auto, schuif 50–100%) | Laadlimiet van de auto instellen, in stappen van 10% |
| Auto nu verversen (knop) | Maakt de auto wakker voor verse gegevens (kost 12V-accu, niet vaak automatiseren) |

> Staat je Zaptec in **stand-alone modus**, dan negeert hij de laadstroom uit Home Assistant.
> Zet stand-alone uit in de Zaptec-app als je de stroom wilt regelen.

## Energie-dashboard

1. **Instellingen → Dashboards → Energie → Apparaatverbruik → Apparaat toevoegen**.
2. Kies **Zaptec Go 2 Totaal geladen energie**.

De kostensensoren rekenen elke update de nieuw geladen kWh × de prijs *op dat moment*. Met een
dynamisch tarief (bijv. de prijs-sensor van Tibber, Zonneplan of Nord Pool) kies je die sensor onder
**Configureren → Prijssensor**; anders geldt de vaste prijs. De prijssensor moet de prijs in €/kWh geven.

## Installatie

1. Kopieer `custom_components/kia_zaptec` naar `config/custom_components/` van je Home Assistant.
2. Herstart Home Assistant.

**Daarna**
1. **Instellingen → Apparaten & diensten → Integratie toevoegen → "Kia + Zaptec Laden"**.
2. Vul je Zaptec-portal-login in, daarna je Kia Connect-gegevens.
3. Via **Configureren** stel je de accucapaciteit in (EV2: ~42 kWh standaard, ~61 kWh long range)
   de update-intervallen en de stroomprijs.

Is de Kia-token verlopen, dan meldt Home Assistant **"Opnieuw configureren"**: vul dan je
Zaptec-wachtwoord en een nieuwe refresh token in.

Home Assistant installeert de Kia-bibliotheek
[`hyundai_kia_connect_api`](https://github.com/Hyundai-Kia-Connect/hyundai_kia_connect_api) automatisch.

### Kia Connect in Europa: refresh token

Kia heeft de gewone wachtwoord-login in Europa dichtgezet. Je moet als "wachtwoord" een **refresh token**
invullen. Die haal je op met het token-script / de uitleg van het
[kia_uvo-project](https://github.com/Hyundai-Kia-Connect/kia_uvo/wiki) (log in via de browser, kopieer het token).
Vul je e-mailadres als gebruikersnaam in. De PIN is alleen nodig voor commando's en mag leeg blijven.

### Over de Kia-updates

Standaard leest de integratie alleen de status die al in de Kia-cloud staat. De auto stuurt die zelf door
(tijdens het laden regelmatig). **"Auto wakker maken"** forceert een verse uitlezing, maar dat kost de
12V-accu stroom en Kia beperkt het aantal verzoeken per dag. Gebruik het spaarzaam (bijv. 60 min of 0).

## Voorbeeld-dashboard

```yaml
type: entities
title: Laden
entities:
  - entity: sensor.zaptec_go_2_status_laadpaal
  - entity: sensor.zaptec_go_2_laadvermogen
  - entity: sensor.zaptec_go_2_beschikbaar_vermogen_voor_auto
  - entity: sensor.zaptec_go_2_energie_deze_sessie
  - entity: sensor.kia_ev2_accu
  - entity: sensor.kia_ev2_laadlimiet_ac
  - entity: sensor.kia_ev2_energie_tot_laadlimiet
  - entity: sensor.kia_ev2_tijd_tot_laadlimiet_live
  - entity: switch.zaptec_go_2_laden_toegestaan
  - entity: number.zaptec_go_2_maximale_laadstroom
  - entity: number.kia_ev2_laadlimiet_ac
  - entity: sensor.zaptec_go_2_kosten_deze_sessie
```
(De entity-id's hangen af van de naam van je apparaten; controleer ze onder Apparaten.)

## Beperkingen / volgende stappen
- Zaptec wordt gepolld (geen push). 15 s is prima; lager dan 5 s heeft geen zin.
- Kia-accounts die om een eenmalige code (OTP) vragen worden nog niet ondersteund.
