local core = import 'core.libsonnet';
local systeminit = import '../systeminit.libsonnet';

{
  images: core.images + {
    REGISTRY_IMAGE: 'petroud/stelar-tuc:registry',
    REGISTRY_INIT: 'petroud/stelar-tuc:registry-init',
    VISUALIZER_IMAGE: 'petroud/profvisualizer:latest',
    SDE_MANAGER_IMAGE: 'petroud/sde-manager:latest',
    PREVIEWER_IMAGE: 'petroud/stelar-previewer:latest',
    LLM_SEARCH_IMAGE: 'petroud/semantic-dataset-search:latest',
  },

  components: core.baseComponents + [
    import '../registry.libsonnet',
    import '../visualizer.libsonnet',
    import '../previewer.libsonnet',
    systeminit('full'),
  ],
}
