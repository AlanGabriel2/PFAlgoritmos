from level import load_combat_level


def test_s10_deja_que_los_proyectiles_crucen_los_solidos():
    assert load_combat_level("s10").projectiles_collide_with_solids is False


def test_otros_niveles_mantienen_la_colision_de_proyectiles():
    assert load_combat_level("s9").projectiles_collide_with_solids is True
