import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../schemas/template.dart';
import 'home_notifier.dart';

const double _tileMaxWidth = 220;

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  final _searchController = TextEditingController();

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _openCustom() {
    final text = _searchController.text.trim();
    final location = Uri(
      path: '/create',
      queryParameters: text.isEmpty ? null : {'prompt': text},
    );
    context.push(location.toString());
  }

  @override
  Widget build(BuildContext context) {
    final templates = ref.watch(homeNotifierProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Trending'),
        actions: [
          IconButton(
            icon: const Icon(Icons.account_circle_outlined),
            tooltip: 'Profile',
            onPressed: () => context.push('/profile'),
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Column(
          children: [
            const SizedBox(height: 8),
            TextField(
              controller: _searchController,
              textInputAction: TextInputAction.search,
              decoration: const InputDecoration(
                hintText: 'Search styles',
                prefixIcon: Icon(Icons.search),
                border: OutlineInputBorder(),
              ),
              onChanged: ref.read(homeNotifierProvider.notifier).setQuery,
            ),
            const SizedBox(height: 12),
            _CreateOwnCard(onTap: _openCustom),
            const SizedBox(height: 12),
            Expanded(
              child: templates.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (_, _) => _ErrorView(
                  onRetry: ref.read(homeNotifierProvider.notifier).retry,
                ),
                data: (items) => items.isEmpty
                    ? const Center(child: Text('No templates match your search.'))
                    : _TemplateGrid(templates: items),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CreateOwnCard extends StatelessWidget {
  const _CreateOwnCard({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: ListTile(
        leading: const Icon(Icons.auto_awesome),
        title: const Text('Create your own'),
        subtitle: const Text('Write your own prompt'),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('Could not load templates.'),
          const SizedBox(height: 12),
          FilledButton(onPressed: onRetry, child: const Text('Retry')),
        ],
      ),
    );
  }
}

class _TemplateGrid extends StatelessWidget {
  const _TemplateGrid({required this.templates});

  final List<TemplateSummary> templates;

  @override
  Widget build(BuildContext context) {
    return GridView.builder(
      gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
        maxCrossAxisExtent: _tileMaxWidth,
        mainAxisSpacing: 12,
        crossAxisSpacing: 12,
        childAspectRatio: 0.85,
      ),
      itemCount: templates.length,
      itemBuilder: (context, index) {
        final template = templates[index];
        return _TemplateTile(
          template: template,
          onTap: () => context.push('/template/${template.id}', extra: template),
        );
      },
    );
  }
}

class _TemplateTile extends StatelessWidget {
  const _TemplateTile({required this.template, required this.onTap});

  final TemplateSummary template;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: SizedBox.expand(
                child: Image.network(
                  template.previewUrl,
                  fit: BoxFit.cover,
                  errorBuilder: (_, _, _) =>
                      const ColoredBox(color: Colors.black12, child: Icon(Icons.image_not_supported_outlined)),
                ),
              ),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            template.title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.titleSmall,
          ),
        ],
      ),
    );
  }
}
