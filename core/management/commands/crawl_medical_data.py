from django.core.management.base import BaseCommand, CommandError

from core.crawler import CrawlConfig, ZYSJ_INDEX_URL, ZYSJ_SOURCE_NAME, crawl, crawl_zysj_herbs
from core.logging import log_operation


class Command(BaseCommand):
    help = "默认低频采集中医世家中药学目录（最多 20 条）；也可通过 URL 和 CSS 选择器采集其他公开列表。"

    def add_arguments(self, parser):
        parser.add_argument("--url", action="append", default=[], help="公开列表页，可重复传入")
        parser.add_argument("--item-selector", default="", help="每条文章的 CSS 选择器")
        parser.add_argument("--title-selector", default="", help="条目内标题的 CSS 选择器")
        parser.add_argument("--link-selector", default="a[href]")
        parser.add_argument("--category-selector", default="")
        parser.add_argument("--symptom-selector", default="")
        parser.add_argument("--department-selector", default="")
        parser.add_argument("--date-selector", default="")
        parser.add_argument("--text-selector", default="")
        parser.add_argument("--source-name", default="")
        parser.add_argument("--delay", type=float, default=1.0)
        parser.add_argument("--max-items", type=int, default=20)

    def handle(self, *args, **options):
        if not options["url"]:
            try:
                created, duplicates, errors = crawl_zysj_herbs(
                    max_items=options["max_items"], delay=max(2.0, options["delay"])
                )
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            log_operation(None, "数据采集", "采集", ZYSJ_SOURCE_NAME,
                          f"新增 {created}，重复 {duplicates}，失败 {len(errors)}；来源：{ZYSJ_INDEX_URL}")
            for error in errors:
                self.stderr.write(self.style.WARNING(error))
            self.stdout.write(f"采集完成：新增 {created}，重复 {duplicates}，失败详情 {len(errors)}。")
            return
        config = CrawlConfig(
            urls=tuple(options["url"]), item_selector=options["item_selector"],
            title_selector=options["title_selector"], source_name=options["source_name"],
            link_selector=options["link_selector"], category_selector=options["category_selector"],
            symptom_selector=options["symptom_selector"], department_selector=options["department_selector"],
            date_selector=options["date_selector"], text_selector=options["text_selector"],
            delay=options["delay"], max_items=options["max_items"],
        )
        try:
            created, duplicates, errors = crawl(config)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        log_operation(None, "数据采集", "采集", config.source_name,
                      f"新增 {created}，重复 {duplicates}，失败 {len(errors)}；来源：{', '.join(config.urls)}")
        for error in errors:
            self.stderr.write(self.style.WARNING(error))
        self.stdout.write(f"采集完成：新增 {created}，重复 {duplicates}，失败页面 {len(errors)}。")
