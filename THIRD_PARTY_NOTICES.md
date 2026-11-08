# Third-party notices

2026-11-07

Luomu CAD distributes the following licensed component code. This notice accompanies the source and release packages.

## Optional solid-model runtime

AgentCAD 0.7.2, maintained by James Dillard, is used unmodified through its CLI in a separate environment. Repository: https://github.com/jdilla1277/agentcad, reviewed revision edf3805169afa6651d9e5961e7e8bf8ae74ee6b3, license Apache-2.0. AgentCAD, build123d and their binary dependencies are installed separately and are not bundled in this repository or its source releases. Their distribution licenses and notices remain in that environment. Luomu CAD owns the interface adapter, requirement gate, evidence binding and archive code. No AgentCAD implementation is relicensed as Luomu CAD code.

Reviewed implementation references:

- [Feature checks](https://github.com/jdilla1277/agentcad/blob/edf3805169afa6651d9e5961e7e8bf8ae74ee6b3/src/agentcad/commands/check_spec.py)
- [Source-frame Boolean comparison](https://github.com/jdilla1277/agentcad/blob/edf3805169afa6651d9e5961e7e8bf8ae74ee6b3/src/agentcad/solid_compare.py)
- [Workflow guide](https://github.com/jdilla1277/agentcad/blob/edf3805169afa6651d9e5961e7e8bf8ae74ee6b3/src/agentcad/guide.py)

## CAD component library

### Component reference documents

Reviewed on 2026-11-06 at commit 5f55f7f79d6b27dad3e7c0ece5f5f677ad70b0e5; the first two records were collected at 2026-11-06T20:09:01+08:00.

- [DXF layout reading](https://github.com/ZWD11/house-plan-designer/blob/5f55f7f79d6b27dad3e7c0ece5f5f677ad70b0e5/reference/route-dxf-layout.md)
- [Dimension references and drawing checks](https://github.com/ZWD11/house-plan-designer/blob/5f55f7f79d6b27dad3e7c0ece5f5f677ad70b0e5/reference/workflow-check.md)
- [CAD conventions](https://github.com/ZWD11/house-plan-designer/blob/5f55f7f79d6b27dad3e7c0ece5f5f677ad70b0e5/reference/cad-conventions.md)

### Component license

The component drawing and wall geometry functions in `scripts/cad_component_library.mjs` include code from the project identified below. Integration, native CAD conversion, validation, and packaging are maintained by Luomu CAD.

MIT License

Copyright (c) 2026 ZWD11

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Pinned ZWD11/house-plan-designer commit 5f55f7f79d6b27dad3e7c0ece5f5f677ad70b0e5.
Extracted pure component functions from assets/template.html.
Adaptations: explicit exterior side, unsupported raster patterns/external images fail visibly.
Original upstream identifiers retained for source comparison.

### Source record

```json
{
  "repository": "https://github.com/ZWD11/house-plan-designer",
  "commit": "5f55f7f79d6b27dad3e7c0ece5f5f677ad70b0e5",
  "source": "assets/template.html",
  "date": "2026-11-07",
  "source_sha256": "11f2dd7298bae8b84adf9bd74f1d41c79959631d8bfc28300b0e6cdd0a1a128c",
  "license": "MIT, Copyright (c) 2026 ZWD11",
  "functions": [
    {
      "name": "_e",
      "sha256": "4ce37b6bdaf31ed16402d86f70de556e98d3c070f03e574d627874fc7ccc1dfc"
    },
    {
      "name": "fs",
      "sha256": "cf75e063176287c8390d54dcbecdac0b81c03c96047d82fb3fa9d2c38c068845"
    },
    {
      "name": "hr",
      "sha256": "70f0820b731c03a3771643e3d883806ad147a41e2cdf7b0e0e35f90cdf964e60"
    },
    {
      "name": "Lh",
      "sha256": "da58e49ef3ac6a536731b0cd1025be584a49f420ecd172ba23047666ab1fc5ad"
    },
    {
      "name": "V3",
      "sha256": "ee92cf05b1e95c664588eafd45ac42d6bc4b62575212c948a9a7e32a0cdfb549"
    },
    {
      "name": "BT",
      "sha256": "7e1870c13d86a618d3630cfd88f40565aec9a1f8fe7fc6d0fc1be6c48d30832f"
    },
    {
      "name": "zT",
      "sha256": "0434f8f9d404e980c4d1c1b2702876268800ba309ef1ca99353bddea66d69d0c"
    },
    {
      "name": "HT",
      "sha256": "c15cc02c1df14cfebd06210ac32964fc0f1af8ec665eaec26f9f3d4e9d92a89b"
    },
    {
      "name": "Jv",
      "sha256": "ddce16b83b7dd54dc4f1d37b54e2117e556ac3ab42044659984e80d278ce5bc0"
    },
    {
      "name": "v1",
      "sha256": "6ade926cc076f090be9b1e2d2256d33a2f46815c1c24ae14ef4ec27787d25415"
    },
    {
      "name": "ki",
      "sha256": "c0ab0a98d608c8d811d8ef0c507156fa18b38bcf19b28a81e6688283032b488b"
    },
    {
      "name": "Lf",
      "sha256": "c675c671dca0c581c583284e4f8f0cbcfb0b38ffc5f443f2dbe992ef32eff441"
    },
    {
      "name": "cu",
      "sha256": "d9d64730400b6e5351468cc72520c9e10042c41f6e2ec7d3522d07c36a90e8f9"
    },
    {
      "name": "Ce",
      "sha256": "bb558a28e661545b9b64827b6c1649ef51de987894485e85c972b5c56957b7dc"
    },
    {
      "name": "V1",
      "sha256": "0fb9a6e915e958cdc033732c8952e579015b0e2f4c1d30014734b8b278171ffb"
    },
    {
      "name": "jT",
      "sha256": "a1d95ddceb343741309891aab9bedb1d8dd52746105194a7b2a6f5953f3583c3"
    },
    {
      "name": "km",
      "sha256": "5b3a8e6293919585c22aeb85968b3270dbdd3fec464aa5bd0778d72697672436"
    },
    {
      "name": "Ml",
      "sha256": "1634d79329a12d974e965696e8b9a79f4a797b8eb77bbf45d8c9656934e4214d"
    },
    {
      "name": "XT",
      "sha256": "90e3bf19e649fef2ebcc4faf86454e4576e29fdc6b88e4c6cfe5a645a338d04f"
    },
    {
      "name": "is",
      "sha256": "3d30e3f247798ccf57cf0823a6dd35c745861e7ae69a98647fcbd3f04c58cbbe"
    },
    {
      "name": "bo",
      "sha256": "dc638c07aba0885ad5aee427c52f81f2263c278f9840ed9ee118acaddf7492cd"
    },
    {
      "name": "Wi",
      "sha256": "47615bf60b40bee2de87f5c9786df647f7ac1238e9b3972a8e6dac481b4b6aba"
    },
    {
      "name": "tx",
      "sha256": "a2b614339c9c74fe8837ca9902121c68eb02bf26ad965e18e2760b283c04c0f6"
    },
    {
      "name": "of",
      "sha256": "8af9ff42fdc67ac188a6f3b6eaa3282ea27834f44e0167677d4d0200de531891"
    },
    {
      "name": "Xt",
      "sha256": "ff177318504ada3d919088dbc74beb3d770097925c63706fdc1c291a341fb431"
    },
    {
      "name": "Pm",
      "sha256": "84f9097e4dac8ee9dabc416295dff7bcc0a280dc37e05718d2e3d6fcfc3920ea"
    },
    {
      "name": "nx",
      "sha256": "5eb9e095eb035ba4e59c202c0eec5c6389a75edbbab82693a9cfe607dbd07513"
    },
    {
      "name": "gh",
      "sha256": "53a50794742b22f94ad2743b23c5dab392a92641e2673d4dcb91d356665a5779"
    },
    {
      "name": "Dl",
      "sha256": "3cc4793dc044f791f39e476c383bb6bf537fb7166c6c03a57246a81c124606f7"
    },
    {
      "name": "JT",
      "sha256": "7d340e9d8f2d4c149be602b87eaf197b3d735aaa74548cbfe540819b6b4bd710"
    },
    {
      "name": "p0",
      "sha256": "8387601a888dda29d2beeb3f8d9a78d195b85305b492bdae4034deeba508769e"
    },
    {
      "name": "R6",
      "sha256": "312ef43cb9ac2af1aaee6911046e9c7123ce69bbc9298da75927f6ed051dfee3"
    },
    {
      "name": "qL",
      "sha256": "478cb66afd707aecf813ea01c8f28f8d7005e9709c447af670b27e2821e92069"
    },
    {
      "name": "Lt",
      "sha256": "4ffea829b31869eef7095350cab77a61860ae8be9984a2836a5f07741a0442a4"
    },
    {
      "name": "ql",
      "sha256": "318e82083980d04086fbcee487500fd530b72e5dd12815482dc4a262c6a40ace"
    },
    {
      "name": "d8",
      "sha256": "7f1b02e86a1387cdcd67719833a4a8993e1b61e67d0bc9fc5e08c8dd95fc87de"
    },
    {
      "name": "g5",
      "sha256": "da8ae74b2598bc855907340f509559561fa99239fa319b9bc3628481860f0a95"
    },
    {
      "name": "ga",
      "sha256": "eec58905499427cca3b55fe19a3f97b0bd517f1b28291e82887dcc892b19ca05"
    },
    {
      "name": "m8",
      "sha256": "0654554d5e00dfdc02de25e6c8560a316ed70f04f1513003489b64714502fa0b"
    },
    {
      "name": "qw",
      "sha256": "e9df483222fcf4abc36908468273e33619c64a8aaeafefedce76e1564bd21b50"
    },
    {
      "name": "Xw",
      "sha256": "ab1c0fada46f77051a882cbc3e349051969a03ea2c8139f3fe1f102f7627d096"
    },
    {
      "name": "Pr",
      "sha256": "7fa18406e9dc37b779d7a03372bba857c40f550700992da5d4a686bc04f804b4"
    },
    {
      "name": "Kw",
      "sha256": "f1603c1294a22c92bfb364a269ba2590e10bcbefea6eb9fe787bbda30760a5f0"
    },
    {
      "name": "WI",
      "sha256": "01a5ccfa287af7114f84fc6413ff667eb9ffbc1e4fa10d3a11ea02fa94e2a4ef"
    },
    {
      "name": "Zw",
      "sha256": "5698291e326302b6e13a0b6fe89aacc8c9a1c9290be8fb64a4f7006f861b0c3d"
    },
    {
      "name": "f3",
      "sha256": "62bc6af75c56891aa2cc0b503143e6f528d57c2d2574435d929f942bb3697a50"
    },
    {
      "name": "$I",
      "sha256": "81fb016dbd5095b0cced623f1b02d1516b706f98fd13d74c8e9906853b32604c"
    },
    {
      "name": "ml",
      "sha256": "e466f126f40bfe46f1a59c60e4e0a1861a928b92c03e413d9520bb6c6d1935ac"
    },
    {
      "name": "v8",
      "sha256": "1018f3b839725d9df77daa3e95da3073f12a3c010ed3a14122ad7e339af92972"
    }
  ],
  "adapters": [
    "lr",
    "h8",
    "II"
  ]
}
```
