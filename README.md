# Paternoster

[![CI](https://github.com/palfrey/paternoster/actions/workflows/ci.yml/badge.svg)](https://github.com/palfrey/paternoster/actions/workflows/ci.yml)

Paternoster is a tool for helping you determine when the train station you're going to doesn't have working lifts, and is named after the [continually moving lift type](https://en.wikipedia.org/wiki/Paternoster_lift).

It uses data from the [Tfl Unified API](https://api.tfl.gov.uk/) and the [Network Rail Lifts & Escalators API](https://nr-lift-and-escalator.developer.azure-api.net/), and so has data for lifts in both London and the wider UK.

There is a live instance at https://paternoster.herokuapp.com/

## Local installation

1. `pip install -r requirements.txt`
2. `make debug`

## Acknowledgements

Thanks to obviously [TfL](https://tfl.gov.uk/) and [National Rail](https://www.nationalrail.co.uk/) for providing the APIs, as well as the [Open Rail Data Wiki](https://wiki.openraildata.com/) for docs on those and [Up Down London](https://www.updownlondon.com/) for further hints on use of them.
