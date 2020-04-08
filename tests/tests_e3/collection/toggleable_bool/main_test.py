from e3.collection.toggleable_bool import ToggleableBooleanGroup


def test_toggleable_bools():
    g = ToggleableBooleanGroup()
    for i, v in enumerate((True, True, False, True, False, False)):
        g.add(name="seed{}".format(i), value=v)

    result = []
    result.append([bool(c) for c in g])
    for series in g.shuffle():
        result.append([bool(c) for c in series])
        assert series == list(g)
        assert len(g) == 6

    assert result == [
        [True, True, False, True, False, False],
        [True, True, True, True, True, True],
        [True, True, True, True, True, False],
        [True, True, True, True, False, True],
        [True, True, True, True, False, False],
        [True, True, True, False, True, True],
        [True, True, True, False, True, False],
        [True, True, True, False, False, True],
        [True, True, True, False, False, False],
        [True, True, False, True, True, True],
        [True, True, False, True, True, False],
        [True, True, False, True, False, True],
        [True, True, False, False, True, True],
        [True, True, False, False, True, False],
        [True, True, False, False, False, True],
        [True, True, False, False, False, False],
        [True, False, True, True, True, True],
        [True, False, True, True, True, False],
        [True, False, True, True, False, True],
        [True, False, True, True, False, False],
        [True, False, True, False, True, True],
        [True, False, True, False, True, False],
        [True, False, True, False, False, True],
        [True, False, True, False, False, False],
        [True, False, False, True, True, True],
        [True, False, False, True, True, False],
        [True, False, False, True, False, True],
        [True, False, False, True, False, False],
        [True, False, False, False, True, True],
        [True, False, False, False, True, False],
        [True, False, False, False, False, True],
        [True, False, False, False, False, False],
        [False, True, True, True, True, True],
        [False, True, True, True, True, False],
        [False, True, True, True, False, True],
        [False, True, True, True, False, False],
        [False, True, True, False, True, True],
        [False, True, True, False, True, False],
        [False, True, True, False, False, True],
        [False, True, True, False, False, False],
        [False, True, False, True, True, True],
        [False, True, False, True, True, False],
        [False, True, False, True, False, True],
        [False, True, False, True, False, False],
        [False, True, False, False, True, True],
        [False, True, False, False, True, False],
        [False, True, False, False, False, True],
        [False, True, False, False, False, False],
        [False, False, True, True, True, True],
        [False, False, True, True, True, False],
        [False, False, True, True, False, True],
        [False, False, True, True, False, False],
        [False, False, True, False, True, True],
        [False, False, True, False, True, False],
        [False, False, True, False, False, True],
        [False, False, True, False, False, False],
        [False, False, False, True, True, True],
        [False, False, False, True, True, False],
        [False, False, False, True, False, True],
        [False, False, False, True, False, False],
        [False, False, False, False, True, True],
        [False, False, False, False, True, False],
        [False, False, False, False, False, True],
        [False, False, False, False, False, False],
    ]
