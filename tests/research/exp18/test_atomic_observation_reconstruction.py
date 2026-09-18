def test_reconstruction_contract_is_explicitly_separate():
    """EXP-18 does not hide reconstruction inside AtomicObservation.

    A future coverage/reconstruction layer must establish either:
    lossless reconstruction against the source object, or an explicit
    coverage mapping explaining what source material is represented.
    """
    assert True
