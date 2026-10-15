import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'account_notifier.dart';

/// Compares the plans. There is deliberately no purchase control: payments
/// are not built yet, and the screen must not imply otherwise.
class UpgradeScreen extends ConsumerWidget {
  const UpgradeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final limits = ref.watch(accountProvider).valueOrNull?.usage?.planLimits ?? const {};
    return Scaffold(
      appBar: AppBar(title: const Text('Upgrade')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (limits.isNotEmpty) ...[
            _PlanRow(
              name: 'Free',
              detail: '${limits['free']} generations per day',
            ),
            const SizedBox(height: 12),
            _PlanRow(
              name: 'Premium',
              detail: '${limits['premium']} generations per day',
              highlighted: true,
            ),
            const SizedBox(height: 24),
          ],
          const Card(
            child: ListTile(
              leading: Icon(Icons.info_outline),
              title: Text('Payments are not available yet'),
              subtitle: Text(
                'Premium cannot be purchased in the app for now.',
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PlanRow extends StatelessWidget {
  const _PlanRow({
    required this.name,
    required this.detail,
    this.highlighted = false,
  });

  final String name;
  final String detail;
  final bool highlighted;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      color: highlighted ? scheme.primaryContainer : null,
      child: ListTile(
        leading: Icon(highlighted ? Icons.workspace_premium : Icons.person_outline),
        title: Text(name),
        subtitle: Text(detail),
      ),
    );
  }
}
