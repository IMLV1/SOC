import asyncio
from uuid import uuid4

import pytest

from app.evaluation.real_experiment import execute_arm


def test_arm_c_fails_closed_until_dify_contract_is_integrated():
    with pytest.raises(RuntimeError, match="DIFY_EXPERIMENT_ADAPTER_UNAVAILABLE"):
        asyncio.run(execute_arm(None, uuid4()))
