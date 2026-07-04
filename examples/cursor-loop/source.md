# Grid-Scale Battery Storage — Reference Sheet

*This is the only source of truth for the demo. Answers should be grounded in this file.*

- A grid-scale battery stores electricity when supply exceeds demand and discharges it when demand exceeds supply. It acts as a buffer — a "shock absorber" — for the grid.

- A storage asset is described by two numbers: **power** (MW — how fast it can charge or discharge) and **energy capacity** (MWh — how much it can store). A 100 MW / 400 MWh battery can deliver 100 MW for 4 hours.

- **State of Health (SoH)** measures how much of a battery's original capacity remains. A battery is typically considered end-of-life when its SoH falls below **80%** of the original capacity.

- Degradation has two main drivers: **calendar aging** (time and temperature) and **cycle aging** (the number and depth of charge/discharge cycles). Deep cycles and high temperatures accelerate degradation.

- **Predictive maintenance** uses sensor data (voltage, current, temperature) to anticipate cell failures before they cascade, instead of replacing parts on a fixed schedule.

- **Real-time dispatch optimization** decides, minute by minute, whether to charge, discharge, or hold — balancing the electricity price, grid-frequency needs, and the degradation cost that each action causes.

- A **digital twin** is a live model of the physical asset, kept in sync with sensor data, used to plan and stress-test decisions before applying them to the real battery.
