from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.domain.ports import ClassifierPort, GmailPort
from app.domain.repositories import EmailRepository
from app.workflows.email_pipeline import nodes
from app.workflows.email_pipeline.state import EmailState


def build_pipeline_graph(
    gmail: GmailPort,
    classifier: ClassifierPort,
    email_repository: EmailRepository,
    force_reprocess: bool = False,
) -> CompiledStateGraph:
    graph = StateGraph(EmailState)

    graph.add_node(
        "check_existing", nodes.make_check_existing_node(email_repository, force_reprocess)
    )
    graph.add_node("classify", nodes.make_classify_node(classifier))
    graph.add_node("fetch_body", nodes.make_fetch_body_node(gmail))
    graph.add_node("reclassify", nodes.make_reclassify_node(classifier))
    graph.add_node("save", nodes.make_save_node(email_repository))

    graph.set_entry_point("check_existing")
    graph.add_conditional_edges(
        "check_existing",
        nodes.route_after_check,
        {"classify": "classify", "__end__": END},
    )
    graph.add_conditional_edges(
        "classify",
        nodes.route_after_classify,
        {"fetch_body": "fetch_body", "save": "save"},
    )
    graph.add_edge("fetch_body", "reclassify")
    graph.add_edge("reclassify", "save")
    graph.add_edge("save", END)

    return graph.compile()
