import pygame
pygame.init()
img = pygame.image.load('assets/Enemigo_menu_referencia.png')
w, h = img.get_size()
s = pygame.transform.scale(img, (80, 40))
out = ''
for y in range(s.get_height()):
    for x in range(s.get_width()):
        c = s.get_at((x,y))
        out += '#' if (c[0]+c[1]+c[2]) > 100 else '.'
    out += '\n'
with open('ref_ascii.txt', 'w') as f:
    f.write(out)
