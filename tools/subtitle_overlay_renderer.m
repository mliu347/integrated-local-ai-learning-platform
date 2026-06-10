#import <Cocoa/Cocoa.h>

static NSString *ArgString(int index, int argc, const char *argv[]) {
    if (index >= argc || argv[index] == NULL) {
        return @"";
    }
    NSString *value = [NSString stringWithUTF8String:argv[index]];
    return value == nil ? @"" : value;
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc < 6) {
            fprintf(stderr, "usage: subtitle_overlay_renderer output.png width height english zh\n");
            return 2;
        }

        NSString *outputPath = ArgString(1, argc, argv);
        NSInteger width = MAX(320, [ArgString(2, argc, argv) integerValue]);
        NSInteger height = MAX(240, [ArgString(3, argc, argv) integerValue]);
        NSString *english = ArgString(4, argc, argv);
        NSString *zh = ArgString(5, argc, argv);

        NSBitmapImageRep *bitmap = [[NSBitmapImageRep alloc]
            initWithBitmapDataPlanes:NULL
            pixelsWide:width
            pixelsHigh:height
            bitsPerSample:8
            samplesPerPixel:4
            hasAlpha:YES
            isPlanar:NO
            colorSpaceName:NSDeviceRGBColorSpace
            bytesPerRow:0
            bitsPerPixel:0];

        if (bitmap == nil) {
            fprintf(stderr, "failed to create bitmap\n");
            return 3;
        }

        NSGraphicsContext *context = [NSGraphicsContext graphicsContextWithBitmapImageRep:bitmap];
        [NSGraphicsContext saveGraphicsState];
        [NSGraphicsContext setCurrentContext:context];
        [context setShouldAntialias:YES];

        [[NSColor clearColor] setFill];
        NSRectFillUsingOperation(NSMakeRect(0, 0, width, height), NSCompositingOperationClear);

        CGFloat boxWidth = MIN(width * 0.82, 1060.0);
        CGFloat textWidth = boxWidth - 56.0;
        CGFloat englishSize = width >= 1000 ? 46.0 : 36.0;
        CGFloat zhSize = width >= 1000 ? 38.0 : 30.0;

        NSMutableParagraphStyle *centered = [[NSMutableParagraphStyle alloc] init];
        [centered setAlignment:NSTextAlignmentCenter];
        [centered setLineBreakMode:NSLineBreakByWordWrapping];
        [centered setLineSpacing:2.0];

        NSDictionary *englishAttrs = @{
            NSFontAttributeName: [NSFont boldSystemFontOfSize:englishSize],
            NSForegroundColorAttributeName: [NSColor whiteColor],
            NSParagraphStyleAttributeName: centered
        };
        NSDictionary *zhAttrs = @{
            NSFontAttributeName: [NSFont systemFontOfSize:zhSize],
            NSForegroundColorAttributeName: [NSColor whiteColor],
            NSParagraphStyleAttributeName: centered
        };

        NSRect englishBounds = [english boundingRectWithSize:NSMakeSize(textWidth, CGFLOAT_MAX)
                                                    options:NSStringDrawingUsesLineFragmentOrigin | NSStringDrawingUsesFontLeading
                                                 attributes:englishAttrs];
        NSRect zhBounds = [zh boundingRectWithSize:NSMakeSize(textWidth, CGFLOAT_MAX)
                                          options:NSStringDrawingUsesLineFragmentOrigin | NSStringDrawingUsesFontLeading
                                       attributes:zhAttrs];

        CGFloat englishHeight = ceil(MAX(englishBounds.size.height, englishSize + 8.0));
        CGFloat zhHeight = zh.length > 0 ? ceil(MAX(zhBounds.size.height, zhSize + 6.0)) : 0.0;
        CGFloat gap = zh.length > 0 ? 8.0 : 0.0;
        CGFloat paddingY = 22.0;
        CGFloat boxHeight = englishHeight + zhHeight + gap + paddingY * 2.0;
        CGFloat boxX = (width - boxWidth) / 2.0;
        CGFloat boxY = MAX(42.0, height * 0.12);

        NSBezierPath *boxPath = [NSBezierPath bezierPathWithRoundedRect:NSMakeRect(boxX, boxY, boxWidth, boxHeight)
                                                                xRadius:12.0
                                                                yRadius:12.0];
        [[NSColor colorWithCalibratedWhite:0.0 alpha:0.58] setFill];
        [boxPath fill];

        CGFloat englishY = boxY + boxHeight - paddingY - englishHeight;
        [english drawWithRect:NSMakeRect(boxX + 28.0, englishY, textWidth, englishHeight + 6.0)
                      options:NSStringDrawingUsesLineFragmentOrigin | NSStringDrawingUsesFontLeading
                   attributes:englishAttrs];

        if (zh.length > 0) {
            CGFloat zhY = englishY - gap - zhHeight;
            [zh drawWithRect:NSMakeRect(boxX + 28.0, zhY, textWidth, zhHeight + 6.0)
                     options:NSStringDrawingUsesLineFragmentOrigin | NSStringDrawingUsesFontLeading
                  attributes:zhAttrs];
        }

        [NSGraphicsContext restoreGraphicsState];

        NSData *pngData = [bitmap representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
        if (pngData == nil || ![pngData writeToFile:outputPath atomically:YES]) {
            fprintf(stderr, "failed to write png\n");
            return 4;
        }
    }
    return 0;
}
