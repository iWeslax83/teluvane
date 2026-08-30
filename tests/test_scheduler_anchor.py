from unittest.mock import patch

from teluvane import scheduler, anchor


def test_run_anchor_cycle_runs_when_configured():
    cfg = anchor.AnchorConfig(rpc_url="x", contract_address="0x0", signer_key="0x0")
    with patch.object(scheduler.anchor, "chain_config", return_value=cfg), \
         patch.object(scheduler.anchor, "reconcile_pending") as recon, \
         patch.object(scheduler.anchor, "run_anchor_pass") as run, \
         patch.object(scheduler, "_anchor_due", return_value=True):
        scheduler.run_anchor_cycle()
    recon.assert_called_once()
    run.assert_called_once()


def test_run_anchor_cycle_skips_when_not_configured():
    with patch.object(scheduler.anchor, "chain_config", return_value=None), \
         patch.object(scheduler.anchor, "reconcile_pending") as recon:
        scheduler.run_anchor_cycle()
    recon.assert_not_called()


def test_run_anchor_cycle_skips_pass_when_not_due():
    cfg = anchor.AnchorConfig(rpc_url="x", contract_address="0x0", signer_key="0x0")
    with patch.object(scheduler.anchor, "chain_config", return_value=cfg), \
         patch.object(scheduler.anchor, "reconcile_pending"), \
         patch.object(scheduler.anchor, "run_anchor_pass") as run, \
         patch.object(scheduler, "_anchor_due", return_value=False):
        scheduler.run_anchor_cycle()
    run.assert_not_called()
