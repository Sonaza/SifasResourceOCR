import os
import math
import glob
import shutil
import pyautogui as pag
import pytesseract
from enum import Enum
from PIL import Image, ImageEnhance, ImageDraw, ImageChops, ImageOps
from collections import namedtuple, defaultdict
from dataclasses import dataclass

@dataclass
class Resources:
	memorial  : int
	memento   : int
	autograph : int
	
Rect = namedtuple('Rect', 'x y w h')

class Group(Enum):
	Muse       = 1
	Aqours     = 2
	Nijigasaki = 3
	
class ResourceOCR:
	
	member_groups = {
		Group.Muse       : ['Hanayo', 'Maki', 'Umi', 'Eli', 'Honoka', 'Kotori', 'Rin', 'Nozomi', 'Nico'],
		Group.Aqours     : ['Mari', 'Yoshiko', 'Dia', 'Riko', 'Chika', 'Kanan', 'You', 'Hanamaru', 'Ruby'],
		Group.Nijigasaki : ['Kanata', 'Mia', 'Karin', 'Rina', 'Kasumi', 'Setsuna', 'Ayumu', 'Emma', 'Shizuku', 'Shioriko', 'Ai', 'Lanzhu'],
	}
	
	cell = Rect(0, 0, 302, 164)
	cell_icon_offset = Rect(42, 22, 106, 106)
	cell_held_offset = Rect(165, 70, 135, 45)
	
	def crop_to_cell_corner(self, source_image, intermediate = None):
		# Top left corner of the image should contain the cell corner
		corner_found = False
		for height_offset in [0, 30, 60]:
			crop_rect = (38, 0, 360, 330 + height_offset)
			haystack = source_image.crop(crop_rect)
			if intermediate:
				haystack.save(intermediate)
			
			corner_rect = pag.locate('icon\\cell_corner.png', haystack, confidence=0.95, grayscale=True)
			if corner_rect != None:
				corner_found = True
				break
		
		if not corner_found:
			return False
				
		crop_rect = Rect(38, corner_rect.top, 1852, 950)
		return source_image.crop(crop_rect)
	
	
	def crop_icon_image(self, source_image, col, row):
		icon_rect = Rect(
			col * self.cell.w + self.cell_icon_offset.x,
			row * self.cell.h + self.cell_icon_offset.y,
			col * self.cell.w + self.cell_icon_offset.x + self.cell_icon_offset.w,
			row * self.cell.h + self.cell_icon_offset.y + self.cell_icon_offset.h
		)
		return source_image.crop(icon_rect)
	
	
	def crop_held_image(self, source_image, col, row):
		held_rect = Rect(
			col * self.cell.w + self.cell_held_offset.x,
			row * self.cell.h + self.cell_held_offset.y,
			col * self.cell.w + self.cell_held_offset.x + self.cell_held_offset.w,
			row * self.cell.h + self.cell_held_offset.y + self.cell_held_offset.h
		)
		held_image = source_image.crop(held_rect)
						
		held_image = held_image.convert('L')
		held_image = ImageOps.invert(held_image)
		enhancer = ImageEnhance.Contrast(held_image)
		held_image = enhancer.enhance(2)
		held_image = ImageChops.multiply(held_image, held_image)
		
		held_image = held_image.resize((
			int(held_image.size[0] * 0.8),
			int(held_image.size[1] * 1)
		), Image.BICUBIC)
		
		held_image = self.image_add_border(held_image, 20, 0)
		return held_image
	
	
	def image_to_integer(self, image):
		custom_psm_config = r'--psm 7'
		result = pytesseract.image_to_string(image, config=custom_psm_config)
		result = result.strip().replace(',', '')
		try:
			return int(result)
		except:
			print(result, "not convertible to integer")
		return False


	def image_add_border(self, original_image, border_size = 10, bgcolor=None):
		new_size = (original_image.size[0] + border_size * 2, original_image.size[1] + border_size * 2)
		paste_rect = (border_size, border_size, original_image.size[0] + border_size, original_image.size[1] + border_size)
		
		if bgcolor == None:
			if original_image.mode == 'RGB':
				bgcolor = (0, 0, 0)
			elif original_image.mode == 'L':
				bgcolor = 0
			else:
				raise Exception(f"Image mode '{original_image.mode}' not supported")
		
		new_image = Image.new(original_image.mode, new_size, color=bgcolor)
		new_image.paste(original_image, paste_rect)
		return new_image

	# --------------------------------------------------

	def ocr_memorials(self, sources_by_group):
		output = {}
		for group, source_files in sources_by_group.items():
			remaining_members = set(self.member_groups[group])
			num_rows = len(remaining_members) // 3
			member_types_found = defaultdict(int)
			
			for source_file in source_files:
				source_image = Image.open(source_file)
				source_image = self.crop_to_cell_corner(source_image)
				if source_image == False:
					raise Exception("Couldn't locate cell.")
				source_image.save(f"processed_{group}.png")
				
				print(f"Processing {group:<7}...", end='')
				
				for row in range(0, num_rows):
					for col in range(0, 6):
						icon_image = self.crop_icon_image(source_image, col, row)
						# icon_image.save(f"out\\icon_image_{group}_{row}x{col}.png")
						
						member_found = False
						for member_name in remaining_members:
							for type_index in range(member_types_found[member_name], 2):
								# if member_name == "Nozomi" and row == 1: continue
								# if member_name == "Umi"    and row == 2: continue
								match_rect = pag.locate(f"icon\\memorial_{member_name}_{type_index}.png", icon_image, confidence=0.93, grayscale=False)
								if match_rect != None:
									member_types_found[member_name] += 1
									if member_types_found[member_name] == 2 and type_index == 1:
										remaining_members.remove(member_name)
									member_found = True
									break
							if member_found:
								break
						
						if not member_found:
							continue
						
						held_image = self.crop_held_image(source_image, col, row)
						held_image.save(f"out\\held_image_{group.name}_{row}x{col}.png")
						
						result = self.image_to_integer(held_image)
						# print(f"{col} x {row} |  '{result}'")
						
						if group not in output:
							output[group] = {}
						if member_name not in output[group]:
							output[group][member_name] = Resources(-1, -1, -1)
						
						if type_index == 0:
							output[group][member_name].memorial = result
						elif type_index == 1:
							output[group][member_name].memento  = result
						
					print(".", end='')
				
				print(" Done!")
		
			if remaining_members:
				print(f"Warning! {len(remaining_members)} missing members in {group} : {remaining_members}")
				for member_name in remaining_members:
					print(f"  {member_name:<9} : {member_types_found[member_name]}/2 found")
					if group not in output:
						output[group] = {}
					if member_name not in output[group]:
						output[group][member_name] = [-1, -1]
			else:
				print(f"No missing members in {group}, yay!")
			print()
			
		sorted_output = {}
		for group, members in self.member_groups.items():
			sorted_output[group] = {member: Resources(-1, -1, -1) for member in members}	
			for name in members:
				if name in output[group]:
					sorted_output[group][name] = output[group][name]
		
		return sorted_output

	# --------------------------------------------------
	
	def ocr_autographs(self, source_files):
		output = {}
		handled_members = set()
		remaining_members = set([x for members in self.member_groups.values() for x in members])
		for index, source_file in enumerate(source_files):
			source_image = Image.open(source_file)
			source_image = self.crop_to_cell_corner(source_image)
			if source_image == False:
				raise Exception("Couldn't locate cell.")
			
			print(f"Processing autographs {index + 1}...", end='')
			
			for row in range(0, 4):
				for col in range(0, 6):
					icon_image = self.crop_icon_image(source_image, col, row)
					member_found = False
					for member_name in remaining_members:
						match_rect = pag.locate(f"icon\\autograph\\autograph_{member_name}.png", icon_image, confidence=0.9, grayscale=False)
						if match_rect != None:
							remaining_members.remove(member_name)
							handled_members.add(member_name)
							member_found = True
							break
					
					if not member_found:
						continue
						
					held_image = self.crop_held_image(source_image, col, row)
					result = self.image_to_integer(held_image)
					
					output[member_name] = result
				print(".", end='')
			
			print(" Done!")
		
		if remaining_members:
			print(f"Missing members: {len(remaining_members)}")
			print(remaining_members)
			print()
		else:
			print("No missing members, yay!")
		print()
		
		return output

	# --------------------------------------------------

	def print_results(self, results):
		for group, data in results.items():
			for name, resource in data.items():
				print(f"{name:<10}\t{resource.memorial:<5}\t{resource.memento:<5}\t{resource.autograph}")
			print()
		print()
	
	def do_ocr(self):
		input_memorials, input_autographs = ocr.identify_screenshots()

		results    = self.ocr_memorials(input_memorials)
		autographs = self.ocr_autographs(input_autographs)
		
		for group, data in results.items():
			for name, value in autographs.items():
				if name in data:
					data[name].autograph = value
		
		self.print_results(results)
	
	def identify_screenshots(self):
		screenshot_folder = r"C:\Users\Sonaza\Nox_share\ImageShare\Screenshots"
		nox_screenshots = glob.glob(os.path.join(screenshot_folder, "Screenshot_*.png"))[-15:]
		
		memorials = {group: [] for group in Group}
		autographs = []
		
		for source_file in reversed(nox_screenshots):
			source_image = Image.open(source_file)
			source_image = self.crop_to_cell_corner(source_image, "process/corner_" + os.path.basename(source_file))
			# source_image.save("process/corner_" + os.path.basename(source_file))
			
			# Corner not found but it's not a fatal error
			if source_image == False:
				continue
			
			icon_image = self.crop_icon_image(source_image, 0, 0)
			icon_image.save("process/asdf_" + os.path.basename(source_file))
			
			member_found = False
			for group, members in self.member_groups.items():
				for member_name in members:
					match_rect = pag.locate(f"icon\\memorial_{member_name}_0.png", icon_image, confidence=0.93, grayscale=False)
					if match_rect != None:
						memorials[group].append(source_file)
						member_found = True
						break
				if member_found:
					break
				
			if member_found:
				continue
			
			autograp_found = False
			for group, members in self.member_groups.items():
				for member_name in members:
					match_rect = pag.locate(f"icon\\autograph\\autograph_{member_name}.png", icon_image, confidence=0.92, grayscale=False)
					if match_rect != None:
						autographs.append(source_file)
						autograp_found = True
						break
				if autograp_found:
					break
		
		print(memorials)
		print()
		print(autographs)
		
		return memorials, autographs
		
		
# -----------------------------------------------

# input_memorials  = list(zip(["muse", "aqours", "niji"], nox_screenshots[0:3]))
# input_autographs = list(zip(["auto1", "auto2"], nox_screenshots[3:5]))

ocr = ResourceOCR()
ocr.do_ocr()

