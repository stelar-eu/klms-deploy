local core = import 'core.libsonnet';

{
  images: core.images + {
    ONTOP_IMAGE: 'petroud/stelar-tuc:ontop',
    REGISTRY_IMAGE: 'petroud/stelar-tuc:registry',
    REGISTRY_INIT: 'petroud/stelar-tuc:registry-init',
    VISUALIZER_IMAGE: 'petroud/profvisualizer:latest',
    SDE_MANAGER_IMAGE: 'petroud/sde-manager:latest',
    PREVIEWER_IMAGE: 'petroud/stelar-previewer:latest',
    LLM_SEARCH_IMAGE: 'petroud/semantic-dataset-search:latest',
  },

  // TODO: finalize full tier component list
  components: core.components + [
    import 'ontop.libsonnet',
    import 'registry.libsonnet',
    import 'visualizer.libsonnet',
    import 'previewer.libsonnet',
    import 'init/kcinit_with_registry.libsonnet',
    import 'init/ontopinit.libsonnet',
    import 'init/quayinit.libsonnet',
  ],
}
