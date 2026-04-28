"""Tests for the room template library."""

from livegen.templates.library import TemplateLibrary


class TestTemplateLibrary:
    def test_load(self):
        lib = TemplateLibrary.load()
        assert lib.templates
        assert len(lib.templates) > 50

    def test_summary(self):
        lib = TemplateLibrary.load()
        summary = lib.summary()
        assert summary["total_templates"] > 50
        assert "hub" in summary["by_type"]
        assert "corridor" in summary["by_type"]
        assert "dead_end" in summary["by_type"]

    def test_by_type(self):
        lib = TemplateLibrary.load()
        hubs = lib.by_type("hub")
        assert len(hubs) > 5
        assert all(t.exits >= 4 for t in hubs)

    def test_by_exits(self):
        lib = TemplateLibrary.load()
        singles = lib.by_exits(1)
        assert all(t.exits == 1 for t in singles)
        multi = lib.by_exits(3, 6)
        assert all(3 <= t.exits <= 6 for t in multi)

    def test_by_theme(self):
        lib = TemplateLibrary.load()
        forest = lib.by_theme("forest")
        assert all(t.theme == "forest" for t in forest)

    def test_by_dungeon(self):
        lib = TemplateLibrary.load()
        deku = lib.by_dungeon("Deku Tree")
        assert len(deku) == 12

    def test_hubs_and_dead_ends(self):
        lib = TemplateLibrary.load()
        hubs = lib.hubs()
        dead_ends = lib.dead_ends()
        assert len(hubs) > 0
        assert len(dead_ends) > 0
        assert all(t.exits >= 4 for t in hubs)
        assert all(t.exits == 1 for t in dead_ends)

    def test_template_id(self):
        lib = TemplateLibrary.load()
        t = lib.templates[0]
        assert t.template_id == f"{t.scene}_{t.room_id}"

    def test_patterns(self):
        lib = TemplateLibrary.load()
        assert "hub_and_spoke" in lib.patterns
        assert "linear_chain" in lib.patterns
