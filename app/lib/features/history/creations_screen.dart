import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../schemas/creation.dart';
import '../auth/session_notifier.dart';
import 'creation_store.dart';
import 'history_sync.dart';

const int _gridColumns = 3;
const double _gridSpacing = 4;
const int _thumbnailDecodeWidth = 300;

final _accountDirectoryProvider =
    FutureProvider.autoDispose.family<Directory, String>(
  (ref, userId) => ref.read(creationStoreProvider).accountDirectory(userId),
);

class CreationsScreen extends ConsumerStatefulWidget {
  const CreationsScreen({super.key});

  @override
  ConsumerState<CreationsScreen> createState() => _CreationsScreenState();
}

class _CreationsScreenState extends ConsumerState<CreationsScreen> {
  @override
  void initState() {
    super.initState();
    startHistoryCatchUp(ref);
  }

  @override
  Widget build(BuildContext context) {
    final userId = ref.watch(sessionProvider).valueOrNull?.userId;
    return Scaffold(
      appBar: AppBar(title: const Text('My creations')),
      body: userId == null
          ? const SizedBox.shrink()
          : _CreationsBody(userId: userId),
    );
  }
}

class _CreationsBody extends ConsumerWidget {
  const _CreationsBody({required this.userId});

  final String userId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final creations = ref.watch(creationsProvider(userId));
    final directory = ref.watch(_accountDirectoryProvider(userId));
    return creations.when(
      skipLoadingOnReload: true,
      loading: () => const Center(child: CircularProgressIndicator()),
      // The store reads unreadable data as empty, so an error here is a
      // failure to start; there is nothing better to show than the empty state.
      error: (_, _) => const _EmptyView(),
      data: (items) {
        final folder = directory.valueOrNull;
        if (items.isEmpty) return const _EmptyView();
        if (folder == null) {
          return const Center(child: CircularProgressIndicator());
        }
        return _CreationGrid(creations: items, folder: folder);
      },
    );
  }
}

class _EmptyView extends StatelessWidget {
  const _EmptyView();

  @override
  Widget build(BuildContext context) =>
      const Center(child: Text('Your creations will appear here'));
}

class _CreationGrid extends StatelessWidget {
  const _CreationGrid({required this.creations, required this.folder});

  final List<Creation> creations;
  final Directory folder;

  @override
  Widget build(BuildContext context) {
    return GridView.builder(
      padding: const EdgeInsets.all(_gridSpacing),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: _gridColumns,
        mainAxisSpacing: _gridSpacing,
        crossAxisSpacing: _gridSpacing,
      ),
      itemCount: creations.length,
      itemBuilder: (context, index) {
        final creation = creations[index];
        return InkWell(
          onTap: () => context.push('/creations/${creation.jobId}'),
          child: Image.file(
            File('${folder.path}/${creation.jobId}.png'),
            key: ValueKey(creation.jobId),
            fit: BoxFit.cover,
            cacheWidth: _thumbnailDecodeWidth,
            errorBuilder: (_, _, _) => const ColoredBox(
              color: Colors.black12,
              child: Icon(Icons.broken_image_outlined),
            ),
          ),
        );
      },
    );
  }
}
