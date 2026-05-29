"""Graphviz rendering for feature models."""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Callable, TYPE_CHECKING

from graphviz import Digraph

if TYPE_CHECKING:
    from .feature import Feature


FeatureRenderer = Callable[[Digraph, "Feature", "FeatureRenderer"], Digraph]


def render_feature(
    dot: Digraph, feature: "Feature", child_renderer: FeatureRenderer | None = None
) -> Digraph:
    """Render a feature and its subfeatures to a graphviz Digraph.

    This renderer will render a feature as a table with the feature name,
    tags, and attribute names. It will render subfeature groups as dashed
    ellipses, and edges from the feature to the subfeature groups will
    be labeled with the relationship type. Edges from subfeature groups
    to their member features will have arrowheads determined by the
    relationship type.

    The third argument is a function with the same signature as this function.
    It will be called to render the child features of this feature.
    If None (the default), it is set to this function, which means that
    the whole subtree will be rendered recursively. However, providing a different
    function (e.g., one which renders a feature as a simple node, or one that skips
    some features) will generate a different visualization.

    Parameters:
    - dot: the graphviz Digraph to render to
    - feature: the feature to render
    - children_renderer: a renderer for the child features of this feature.
      This is called for each child feature. If None, this function will be
      called recursively.

    Returns:
    Digraph: the graphviz Digraph with the rendered feature and its subfeatures
    """

    if child_renderer is None:
        child_renderer = render_feature

    edge_arrowhead = {
        "mandatory": "dot",
        "optional": "odot",
        "alternative": "inv",
        "or": "oinv",
    }

    feature_attr = {"shape": "plain"}
    group_attr = {"shape": "ellipse", "style": "dashed"}

    br = '<BR ALIGN="LEFT"/>\n'
    attribute_labels = _format_attribute_labels(feature)

    feature_label = f"""\
<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">
<TR><TD><B>{feature.name}</B></TD></TR>
<TR><TD ALIGN="LEFT">{br.join(feature.tags)}</TD></TR>
<TR><TD ALIGN="LEFT">{br.join(attribute_labels)}</TD></TR>
</TABLE>>"""

    dot.node(feature.fullname, label=feature_label, **feature_attr)

    for group in feature.subfeatures:
        # for each group add the group node
        dot.node(group.fullname, label=group.identifier, **group_attr)
        dot.edge(feature.fullname, group.fullname, arrowhead="none", label=group.rel)
        for subfeature in group.members:
            # add an edge from the group to the subfeature
            # arrow head is determined by the relationship type
            dot.edge(
                group.fullname,
                subfeature.fullname,
                arrowhead=edge_arrowhead[group.rel],
            )
            child_renderer(dot, subfeature, child_renderer)

    return dot


def _format_attribute_labels(feature: "Feature") -> list[str]:
    """Render feature attribute names for Graphviz HTML labels.

    Attributes with fixed defaults are underlined and rendered before attributes
    without defaults. In both groups, the model's original attribute order is kept.
    """

    defaulted: list[str] = []
    non_defaulted: list[str] = []

    for attr_name, attr_spec in feature.attributes.items():
        label = escape(attr_name)
        if isinstance(attr_spec, Mapping) and "default" in attr_spec:
            defaulted.append(f"<U>{label}</U>")
        else:
            non_defaulted.append(label)

    return defaulted + non_defaulted
