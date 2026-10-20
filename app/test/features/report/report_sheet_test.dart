import 'dart:async';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/report/report_sheet.dart';
import 'package:image_edit/services/generation_providers.dart';

import '../../support/app_harness.dart';
import '../../support/fake_api_client.dart';

final _bytes = Uint8List.fromList([9, 8, 7]);

Future<void> _openSheet(WidgetTester tester, FakeApiClient client) async {
  tester.view.physicalSize = const Size(430, 932);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [apiClientProvider.overrideWithValue(client)],
      child: MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => TextButton(
              onPressed: () =>
                  showReportSheet(context, jobId: 'job-7', bytes: _bytes),
              child: const Text('open'),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
}

bool _sendEnabled(WidgetTester tester) =>
    tester
        .widget<FilledButton>(find.widgetWithText(FilledButton, 'Send'))
        .onPressed !=
    null;

void main() {
  testWidgets('Send is disabled until a category is chosen', (tester) async {
    await _openSheet(tester, FakeApiClient());

    expect(_sendEnabled(tester), isFalse);
    await tester.tap(find.text('Violence or gore'));
    await tester.pump();

    expect(_sendEnabled(tester), isTrue);
  });

  testWidgets('all five categories are offered', (tester) async {
    await _openSheet(tester, FakeApiClient());

    for (final label in [
      'Sexual content',
      'Involves a minor',
      'Violence or gore',
      'Hateful content',
      'Other',
    ]) {
      expect(find.text(label), findsOneWidget);
    }
  });

  testWidgets(
    'Send submits the job, category, note and image then thanks the user',
    (tester) async {
      final client = FakeApiClient();
      await _openSheet(tester, client);

      await tester.tap(find.text('Violence or gore'));
      await tester.enterText(find.byType(TextField), '  looks wrong ');
      await tester.pump();
      await tester.tap(find.text('Send'));
      await tester.pumpAndSettle();

      final report = client.submittedReports.single;
      expect(report.jobId, 'job-7');
      expect(report.category, 'violence');
      expect(report.note, 'looks wrong');
      expect(report.imageBytes, _bytes);
      expect(find.text("Thanks, we'll review it."), findsOneWidget);
      expect(find.text('Report this image'), findsNothing);
    },
  );

  testWidgets('the note is limited to 500 code points, as the server counts', (
    tester,
  ) async {
    await _openSheet(tester, FakeApiClient());
    const family = '\u{1F468}\u200D\u{1F469}\u200D\u{1F467}\u200D\u{1F466}';
    final field = find.byType(TextField);
    String text() => tester.widget<TextField>(field).controller!.text;

    await tester.enterText(field, family * 71);
    expect(text().runes.length, 497);
    await tester.enterText(field, family * 72);

    expect(text().runes.length, 497);
  });

  testWidgets('the sheet cannot be dismissed while sending', (tester) async {
    final client = FakeApiClient();
    final pending = Completer<void>();
    client.onSubmitReport = () => pending.future;
    await _openSheet(tester, client);
    await tester.tap(find.text('Other'));
    await tester.pump();
    await tester.tap(find.text('Send'));
    await tester.pump();

    await tester.tapAt(const Offset(10, 10));
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Report this image'), findsOneWidget);

    pending.complete();
    await tester.pumpAndSettle();
    expect(find.text('Report this image'), findsNothing);
    expect(find.text("Thanks, we'll review it."), findsOneWidget);
  });

  testWidgets('while sending, the controls are disabled and a spinner shows', (
    tester,
  ) async {
    final client = FakeApiClient();
    final pending = Completer<void>();
    client.onSubmitReport = () => pending.future;
    await _openSheet(tester, client);
    await tester.tap(find.text('Other'));
    await tester.pump();

    await tester.tap(find.text('Send'));
    await tester.pump();

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(
      tester
          .widget<TextButton>(find.widgetWithText(TextButton, 'Cancel'))
          .onPressed,
      isNull,
    );
    pending.complete();
    await tester.pumpAndSettle();
    expect(client.submittedReports, hasLength(1));
  });

  testWidgets('too many reports is explained and the choices are kept', (
    tester,
  ) async {
    final client = FakeApiClient()
      ..onSubmitReport = () async =>
          throw apiError(429, 'too_many_reports', 'limit');
    await _openSheet(tester, client);
    await tester.tap(find.text('Hateful content'));
    await tester.enterText(find.byType(TextField), 'my note');
    await tester.pump();

    await tester.tap(find.text('Send'));
    await tester.pumpAndSettle();

    expect(
      find.text("You've sent too many reports today. Try again tomorrow."),
      findsOneWidget,
    );
    expect(find.text('Report this image'), findsOneWidget);
    expect(
      tester.widget<TextField>(find.byType(TextField)).controller!.text,
      'my note',
    );
    expect(_sendEnabled(tester), isTrue);
    expect(find.text("Thanks, we'll review it."), findsNothing);
  });

  testWidgets('a network error keeps the sheet open and the values', (
    tester,
  ) async {
    final client = FakeApiClient()
      ..onSubmitReport = () async => throw DioException(
        requestOptions: RequestOptions(path: '/reports'),
        type: DioExceptionType.connectionError,
      );
    await _openSheet(tester, client);
    await tester.tap(find.text('Other'));
    await tester.enterText(find.byType(TextField), 'offline note');
    await tester.pump();

    await tester.tap(find.text('Send'));
    await tester.pumpAndSettle();

    expect(find.text("Couldn't send the report. Try again."), findsOneWidget);
    expect(
      tester.widget<TextField>(find.byType(TextField)).controller!.text,
      'offline note',
    );
    expect(_sendEnabled(tester), isTrue);

    client.onSubmitReport = () async {};
    await tester.tap(find.text('Send'));
    await tester.pumpAndSettle();
    expect(client.submittedReports.last.category, 'other');
    expect(find.text("Thanks, we'll review it."), findsOneWidget);
  });

  testWidgets('Cancel sends nothing and closes the sheet', (tester) async {
    final client = FakeApiClient();
    await _openSheet(tester, client);
    await tester.tap(find.text('Other'));
    await tester.pump();

    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(client.submittedReports, isEmpty);
    expect(find.text('Report this image'), findsNothing);
    expect(find.text("Thanks, we'll review it."), findsNothing);
  });
}
