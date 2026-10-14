import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_edit/features/common/photo_picker_field.dart';
import 'package:image_picker/image_picker.dart';

import '../../support/fake_image_picker.dart';

Future<ProviderContainer> _pump(WidgetTester tester, FakeImagePicker picker) async {
  final container = ProviderContainer(
    overrides: [imagePickerProvider.overrideWithValue(picker)],
  );
  addTearDown(container.dispose);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(
        home: Scaffold(body: Center(child: PhotoPickerField())),
      ),
    ),
  );
  return container;
}

void main() {
  testWidgets('shows the empty state, then the preview after picking', (tester) async {
    final photo = XFile.fromData(tinyPng, name: 'me.png');
    final picker = FakeImagePicker(result: photo);
    final container = await _pump(tester, picker);
    expect(find.text('Add your photo'), findsOneWidget);

    await tester.tap(find.byType(PhotoPickerField));
    await tester.pumpAndSettle();
    expect(find.text('Take photo'), findsOneWidget);
    await tester.tap(find.text('Choose from library'));
    await tester.pumpAndSettle();

    expect(picker.sources, [ImageSource.gallery]);
    expect(container.read(selectedPhotoProvider), same(photo));
    expect(find.text('Change photo'), findsOneWidget);
    expect(find.text('Add your photo'), findsNothing);
  });

  testWidgets('camera failure shows a message and keeps the library option', (tester) async {
    final picker = FakeImagePicker(error: Exception('no camera'));
    final container = await _pump(tester, picker);

    await tester.tap(find.byType(PhotoPickerField));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Take photo'));
    await tester.pumpAndSettle();

    expect(find.textContaining('camera is not available'), findsOneWidget);
    expect(container.read(selectedPhotoProvider), isNull);

    await tester.tap(find.byType(PhotoPickerField));
    await tester.pumpAndSettle();
    expect(find.text('Choose from library'), findsOneWidget);
  });
}
