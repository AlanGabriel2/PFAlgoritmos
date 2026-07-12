import math

import enemy
from enemy import Boss, EnemyBullet, MiniBoss


def build_boss():
    return Boss(400, 300, scale=0.35)


def test_boss_enters_phase_two_once_and_announces_it(monkeypatch):
    played = []
    monkeypatch.setattr(enemy.audio, "play_sfx", lambda *names: played.append(names))
    boss = build_boss()
    boss.bullets.append(EnemyBullet(10, 10, 0))
    boss.hp = boss.max_hp // 2

    boss.move_logic(500, 300)

    assert boss.phase == 2
    assert boss.phase_transition_timer == boss.PHASE_TRANSITION_FRAMES
    assert boss.next_attack == "fan"
    assert boss.bullets == []
    assert ("boss_phase2_voice",) in played

    boss.move_logic(500, 300)
    assert played.count(("boss_phase2_voice",)) == 1


def test_phase_two_fan_fires_three_aimed_salvos(monkeypatch):
    monkeypatch.setattr(enemy.audio, "play_sfx", lambda *names: None)
    boss = build_boss()
    boss.phase = 2
    boss.phase_transition_timer = 0
    boss.next_attack = "fan"
    boss.action_timer = 124

    boss.move_logic(600, 300)  # prepara el abanico
    assert boss.fan_salvos_remaining == 3
    assert boss.next_attack == "radial"

    for _ in range(3):
        boss.fan_salvo_timer = 0
        boss.move_logic(600, 300)

    assert len(boss.bullets) == 12
    assert boss.fan_salvos_remaining == 0
    assert all(b.b_type == "boss" and b.speed == 5.5 for b in boss.bullets)


def test_phase_two_alternates_back_to_radial(monkeypatch):
    monkeypatch.setattr(enemy.audio, "play_sfx", lambda *names: None)
    boss = build_boss()
    boss.phase = 2
    boss.phase_transition_timer = 0
    boss.next_attack = "radial"
    boss.action_timer = 124

    boss.move_logic(600, 300)

    assert len(boss.bullets) == 8
    assert boss.next_attack == "fan"
    assert {round(b.angle, 5) for b in boss.bullets} == {
        round(i * math.pi / 4, 5) for i in range(8)
    }


def test_boss_launch_matches_loaded_cannon_frame(monkeypatch):
    monkeypatch.setattr(enemy.audio, "play_sfx", lambda *names: None)
    boss = build_boss()
    boss.action_timer = 173

    boss.move_logic(600, 300)
    assert boss.controller.current == "attack"
    assert boss.bullets == []

    for _ in range(boss.ATTACK_ANIMATION_LEAD_FRAMES):
        boss.controller.update(dt_ms=1000 / 60)
    boss.action_timer = 189
    boss.move_logic(600, 300)

    assert int(boss.animator.current_frame) == 4
    assert len(boss.bullets) == 8


def test_miniboss_launch_matches_loaded_core_frame(monkeypatch):
    monkeypatch.setattr(enemy.audio, "play_sfx", lambda *names: None)
    miniboss = MiniBoss(400, 300, scale=0.35)
    miniboss.action_timer = 133

    miniboss.move_logic(600, 300)
    assert miniboss.controller.current == "attack"
    assert miniboss.bullets == []

    for _ in range(miniboss.ATTACK_ANIMATION_LEAD_FRAMES):
        miniboss.controller.update(dt_ms=1000 / 60)
    miniboss.action_timer = 149
    miniboss.move_logic(600, 300)

    assert int(miniboss.animator.current_frame) == 4
    assert len(miniboss.bullets) == 1
