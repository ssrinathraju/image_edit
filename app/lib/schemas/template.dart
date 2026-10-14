class TemplateSummary {
  const TemplateSummary({
    required this.id,
    required this.title,
    required this.tags,
    required this.previewUrl,
  });

  final String id;
  final String title;
  final List<String> tags;
  final String previewUrl;

  factory TemplateSummary.fromJson(Map<String, dynamic> json) {
    return TemplateSummary(
      id: json['id'] as String,
      title: json['title'] as String,
      tags: (json['tags'] as List<dynamic>).cast<String>(),
      previewUrl: json['preview_url'] as String,
    );
  }

  TemplateSummary withPreviewUrl(String url) => TemplateSummary(
        id: id,
        title: title,
        tags: tags,
        previewUrl: url,
      );
}
