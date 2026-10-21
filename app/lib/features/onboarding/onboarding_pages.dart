import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'onboarding_store.dart';

class _PageContent {
  const _PageContent(this.icon, this.title, this.body);

  final IconData icon;
  final String title;
  final String body;
}

const List<_PageContent> _pages = [
  _PageContent(
    Icons.auto_awesome,
    'How it works',
    'Pick a trending template or describe your own scene, add a photo of '
        'yourself, and we\'ll create a new image of you.',
  ),
  _PageContent(
    Icons.lock_outline,
    'Your privacy',
    'Your photo is used only for that image and then deleted. Results are '
        'saved on this device, and our copy is deleted after 24 hours.',
  ),
  _PageContent(
    Icons.verified_user_outlined,
    'The rules',
    'You must be 18 or older. Only upload photos of yourself or of people '
        'who agreed. Unsafe content is blocked.',
  ),
];

const Duration _pageAnimation = Duration(milliseconds: 250);

/// The three onboarding pages with Skip, Next and Get started.
class OnboardingPages extends StatefulWidget {
  const OnboardingPages({required this.onDone, super.key});

  final VoidCallback onDone;

  @override
  State<OnboardingPages> createState() => _OnboardingPagesState();
}

class _OnboardingPagesState extends State<OnboardingPages> {
  final _controller = PageController();
  int _index = 0;

  bool get _isLast => _index == _pages.length - 1;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _next() => _controller.nextPage(
        duration: _pageAnimation,
        curve: Curves.easeOut,
      );

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Column(
        children: [
          Align(
            alignment: Alignment.topRight,
            child: TextButton(onPressed: widget.onDone, child: const Text('Skip')),
          ),
          Expanded(
            child: PageView(
              controller: _controller,
              onPageChanged: (index) => setState(() => _index = index),
              children: [for (final page in _pages) _OnboardingPage(page: page)],
            ),
          ),
          _PageDots(count: _pages.length, current: _index),
          Padding(
            padding: const EdgeInsets.all(24),
            child: SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _isLast ? widget.onDone : _next,
                child: Text(_isLast ? 'Get started' : 'Next'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _OnboardingPage extends StatelessWidget {
  const _OnboardingPage({required this.page});

  final _PageContent page;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const SizedBox(height: 48),
          Icon(page.icon, size: 96, color: theme.colorScheme.primary),
          const SizedBox(height: 32),
          Text(
            page.title,
            style: theme.textTheme.headlineSmall,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          Text(
            page.body,
            style: theme.textTheme.bodyLarge,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

class _PageDots extends StatelessWidget {
  const _PageDots({required this.count, required this.current});

  final int count;
  final int current;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Semantics(
      label: 'Page ${current + 1} of $count',
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          for (var i = 0; i < count; i++)
            Container(
              key: ValueKey('onboarding-dot-$i'),
              width: 8,
              height: 8,
              margin: const EdgeInsets.symmetric(horizontal: 4),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: i == current ? colors.primary : colors.outlineVariant,
              ),
            ),
        ],
      ),
    );
  }
}

/// First launch: finishing records onboarding as seen; the router then moves on.
class OnboardingScreen extends ConsumerWidget {
  const OnboardingScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) => Scaffold(
        body: OnboardingPages(
          onDone: () => ref.read(onboardingSeenProvider.notifier).markSeen(),
        ),
      );
}

/// Reopened from the profile: finishing or going back returns there.
class HowItWorksScreen extends StatelessWidget {
  const HowItWorksScreen({super.key});

  void _close(BuildContext context) =>
      context.canPop() ? context.pop() : context.go('/');

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('How it works')),
        body: OnboardingPages(onDone: () => _close(context)),
      );
}
