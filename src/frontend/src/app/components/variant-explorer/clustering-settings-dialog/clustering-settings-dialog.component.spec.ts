import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ClusteringSettingsDialogComponent } from './clustering-settings-dialog.component';

describe('ClusteringSettingsDialogComponent', () => {
  let component: ClusteringSettingsDialogComponent;
  let fixture: ComponentFixture<ClusteringSettingsDialogComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ClusteringSettingsDialogComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(ClusteringSettingsDialogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
