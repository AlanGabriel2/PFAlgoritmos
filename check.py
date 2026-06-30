import pygame
pygame.init()
img = pygame.image.load('assets/boss_sheet.png')
w, h = img.get_size()
print(f"Original size: {w}x{h}")
s = pygame.transform.scale(img, (w//32, h//32))
out = ''
for y in range(s.get_height()):
    for x in range(s.get_width()):
        out += '#' if s.get_at((x,y))[3] > 128 else '.'
    out += '\n'
with open('boss_grid.txt', 'w') as f:
    f.write(out)
