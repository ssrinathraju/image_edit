import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logging/logging.dart';

import 'features/result_ready/result_ready_presenter.dart';
import 'features/result_ready/result_watcher.dart';
import 'router.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  Logger.root.onRecord.listen(
    (record) => debugPrint('${record.level.name} ${record.loggerName}: ${record.message}'),
  );
  await dotenv.load(fileName: '.env');
  runApp(const ProviderScope(child: ImageEditApp()));
}

class ImageEditApp extends ConsumerStatefulWidget {
  const ImageEditApp({super.key});

  @override
  ConsumerState<ImageEditApp> createState() => _ImageEditAppState();
}

class _ImageEditAppState extends ConsumerState<ImageEditApp>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    ref.read(resultReadyPresenterProvider);
    ref.read(resultWatcherProvider);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    ref.read(resultWatcherProvider).updateLifecycle(state);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'image edit',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
        useMaterial3: true,
      ),
      scaffoldMessengerKey: ref.watch(scaffoldMessengerKeyProvider),
      routerConfig: ref.watch(routerProvider),
    );
  }
}
