import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:image_edit/features/home/home_notifier.dart';
import 'package:image_edit/features/home/home_screen.dart';
import 'package:image_edit/schemas/template.dart';
import 'package:image_edit/services/generation_providers.dart';

import '../../support/fake_api_client.dart';

Future<GoRouter> _pump(WidgetTester tester, FakeApiClient client) async {
  final router = GoRouter(
    routes: [
      GoRoute(path: '/', builder: (_, _) => const HomeScreen()),
      GoRoute(
        path: '/template/:id',
        builder: (_, state) => Text('template:${state.pathParameters['id']}'),
      ),
      GoRoute(
        path: '/create',
        builder: (_, state) =>
            Text('create:${state.uri.queryParameters['prompt'] ?? ''}'),
      ),
    ],
  );
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(client),
        homeDebounceProvider.overrideWithValue(const Duration(milliseconds: 10)),
      ],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
  return router;
}

void main() {
  testWidgets('shows the templates in backend order', (tester) async {
    final client = FakeApiClient()
      ..onListTemplates = (_) async => [
            fakeTemplate('b', title: 'Second Look'),
            fakeTemplate('a', title: 'First Look'),
          ];
    await _pump(tester, client);

    final first = tester.getTopLeft(find.text('Second Look'));
    final second = tester.getTopLeft(find.text('First Look'));
    expect(first.dy, second.dy);
    expect(first.dx, lessThan(second.dx));
    expect(find.text('Create your own'), findsOneWidget);
  });

  testWidgets('tapping a template opens its screen', (tester) async {
    final client = FakeApiClient()
      ..onListTemplates = (_) async => [fakeTemplate('beach', title: 'Beach')];
    await _pump(tester, client);

    await tester.tap(find.text('Beach'));
    await tester.pumpAndSettle();

    expect(find.text('template:beach'), findsOneWidget);
  });

  testWidgets('empty results still offer Create your own', (tester) async {
    final client = FakeApiClient()..onListTemplates = (_) async => const [];
    await _pump(tester, client);

    expect(find.text('No templates match your search.'), findsOneWidget);
    expect(find.text('Create your own'), findsOneWidget);
  });

  testWidgets('search text is carried into the custom flow', (tester) async {
    final client = FakeApiClient()
      ..onListTemplates = (q) async => q == null ? [fakeTemplate('a')] : const <TemplateSummary>[];
    await _pump(tester, client);

    await tester.enterText(find.byType(TextField), 'astronaut on mars');
    await tester.pump(const Duration(milliseconds: 50));
    await tester.pumpAndSettle();
    expect(client.queries.last, 'astronaut on mars');

    await tester.tap(find.text('Create your own'));
    await tester.pumpAndSettle();

    expect(find.text('create:astronaut on mars'), findsOneWidget);
  });

  testWidgets('load failure shows Retry that reloads', (tester) async {
    var calls = 0;
    final client = FakeApiClient()
      ..onListTemplates = (_) async {
        calls++;
        if (calls == 1) throw StateError('offline');
        return [fakeTemplate('beach', title: 'Beach')];
      };
    await _pump(tester, client);

    expect(find.text('Could not load templates.'), findsOneWidget);
    expect(find.text('Create your own'), findsOneWidget);

    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();

    expect(find.text('Beach'), findsOneWidget);
  });
}
