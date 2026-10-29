-- Layer #33 (docs/layers/interconnectors): DK1 physical flow per border,
-- + = import (tested against settlement per border). No capacity series:
-- none is published openly on Energi Data Service (RISK.md).
insert into series (series_id, source_id, code, name, unit, frequency) values
    ('energinet.dk1.flow_de_mw', 'energinet', 'ElectricityProdex5MinRealtime.ExchangeGermany.DK1',
     'DK1 physical flow with Germany, + = import, ISP mean', 'MW', '15min'),
    ('energinet.dk1.flow_nl_mw', 'energinet', 'ElectricityProdex5MinRealtime.ExchangeNetherlands.DK1',
     'DK1 physical flow with the Netherlands (COBRA), + = import, ISP mean', 'MW', '15min'),
    ('energinet.dk1.flow_gb_mw', 'energinet', 'ElectricityProdex5MinRealtime.ExchangeGreatBritain.DK1',
     'DK1 physical flow with Great Britain (Viking Link), + = import, ISP mean', 'MW', '15min'),
    ('energinet.dk1.flow_no_mw', 'energinet', 'ElectricityProdex5MinRealtime.ExchangeNorway.DK1',
     'DK1 physical flow with Norway (Skagerrak), + = import, ISP mean', 'MW', '15min'),
    ('energinet.dk1.flow_se_mw', 'energinet', 'ElectricityProdex5MinRealtime.ExchangeSweden.DK1',
     'DK1 physical flow with Sweden (Konti-Skan), + = import, ISP mean', 'MW', '15min'),
    ('energinet.dk1.flow_dk2_mw', 'energinet', 'ElectricityProdex5MinRealtime.ExchangeGreatBelt.DK1',
     'DK1 physical flow with DK2 over the Great Belt, + = import, ISP mean', 'MW', '15min');
