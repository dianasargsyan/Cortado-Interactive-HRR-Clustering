import { Injectable } from '@angular/core';
import { ProcessTreeService } from '../processTreeService/process-tree.service';
import { ElectronService } from '../electronService/electron.service';
import { ProcessTree } from 'src/app/objects/ProcessTree/ProcessTree';
import {
  Transform,
  TransformationType,
  Type,
  instanceToPlain,
  plainToInstance,
} from 'class-transformer';
import { Variant } from 'src/app/objects/Variants/variant';
import { VariantService } from '../variantService/variant.service';
import { LogService } from '../logService/log.service';
import { DatePipe } from '@angular/common';
import {
  VariantFilterService,
  VariantFilter,
} from '../variantFilterService/variant-filter.service';
import { VariantQueryService } from '../variantQueryService/variant-query.service';
import { environment } from 'src/environments/environment';
import { isEqualWith } from 'lodash';
import { Observable } from 'rxjs';
import { mergeMap, take, tap } from 'rxjs/operators';
import { BackendService } from '../backendService/backend.service';
import { ClusteringConfig } from 'src/app/objects/ClusteringConfig';
import { TimeUnit } from 'src/app/objects/TimeUnit';
import {
  ActivityDeletion,
  ActivityRenaming,
  LogModification,
  LogModificationType,
  UserDefinedInfixAddition,
  UserDefinedVariantAddition,
  VariantsDeletion,
} from 'src/app/objects/LogModification';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { ContinueLastProjectDialogComponent } from 'src/app/components/dialogs/continue-last-project-dialog/continue-last-project-dialog.component';
import { LoadingOverlayService } from '../loadingOverlayService/loading-overlay.service';
@Injectable({
  providedIn: 'root',
})
export class ProjectService {
  constructor(
    private logService: LogService,
    private processTreeService: ProcessTreeService,
    private variantService: VariantService,
    private variantFilterService: VariantFilterService,
    private variantQueryService: VariantQueryService,
    private backendService: BackendService,
    private loadingOverlayService: LoadingOverlayService,
    private modalService: NgbModal,
    private electronService: ElectronService
  ) {
    try {
      this.electronService
        .readFromUserFolder('latest_project', 'json')
        .then((lastProjectJson) => {
          if (!lastProjectJson) {
            this.getInitialProject();
            return;
          }

          const lastProject = plainToInstance(
            Project,
            JSON.parse(lastProjectJson)
          );

          const modalRef = this.modalService.open(
            ContinueLastProjectDialogComponent
          );

          modalRef.componentInstance.projectName = lastProject.eventlogPath
            .split('/')
            .pop();
          modalRef.result.then(
            () => {
              // on confirmation
              this.loadProject(lastProject);
            },
            () => {
              // on dismiss
              this.getInitialProject();
            }
          );
        });

      this.electronService.checkUnsavedChanges$.subscribe(() => {
        // save already to default project on checking for changes
        this.saveProject(false);

        this.electronService.unsavedChangesStatus(this.unsavedChanges);
      });

      this.electronService.saveProject$.subscribe(() =>
        this.saveProject().then((filePath) => {
          if (filePath) this.electronService.quit();
        })
      );
    } catch (error) {
      console.error('Cannot access user folder.', error);
      this.getInitialProject();
    }
  }

  private getInitialProject() {
    // wait for variants to be loaded
    this.variantService.variants$.pipe(take(2)).subscribe((variants) => {
      const project = this.currentProject;
      this.latestSavedProject = instanceToPlain(project, {
        enableCircularCheck: true,
      });
    });
  }

  private latestSavedProject: Record<string, any>;

  get unsavedChanges(): boolean {
    return !isEqualWith(
      this.latestSavedProject,
      JSON.parse(
        JSON.stringify(
          instanceToPlain(this.currentProject, { enableCircularCheck: true })
        )
      ),
      (a, b, key) => {
        // ignore parent property
        if (key === 'parent') return true;
        return undefined;
      }
    );
  }

  get currentProject(): Project {
    return new Project(
      this.logService.loadedEventLog,
      this.logService.timeGranularity,
      this.logService.logModifications,
      this.processTreeService.currentDisplayedProcessTree,
      this.processTreeService.previousTreeObjects,
      this.processTreeService.treeCacheIndex,
      this.processTreeService.selectedRootNodeID,
      this.variantService.variants,
      this.variantFilterService.variantFilters,
      this.variantQueryService.variantQuery,
      this.variantService.clusteringConfig
    );
  }

  public loadProjectFromFile(file: File) {
    const fileReader = new FileReader();
    fileReader.onload = (e) => {
      const project = plainToInstance(
        Project,
        JSON.parse(fileReader.result.toString())
      );
      this.loadProject(project);
    };
    fileReader.readAsText(file);
  }

  public loadProject(project: Project) {
    this.loadingOverlayService.showLoader('Loading Project ...');
    this.latestSavedProject = instanceToPlain(project);

    let loadingLog: Observable<any>;

    if (project.eventlogPath == 'preload') {
      loadingLog = this.backendService.resetLogCache();
    } else {
      loadingLog = this.backendService.loadEventLogFromFilePath(
        project.eventlogPath
      );
    }

    loadingLog
      .pipe(
        mergeMap(() => this.replayLogModifications(project.logModifications)),
        mergeMap(() =>
          this.backendService.getLogPropsAndUpdateState(
            project.timeGranularity,
            project.eventlogPath
          )
        )
      )
      .subscribe(() => {
        this.restoreProjectAfterLog(project);
        this.loadingOverlayService.hideLoader();
      });
  }

  private restoreProjectAfterLog(project: Project) {
    this.processTreeService.previousTreeObjects = project.processTreeHistory;
    this.processTreeService.treeCacheLength = project.processTreeHistory.length;
    this.processTreeService.treeCacheIndex = project.treeCacheIndex;
    this.processTreeService.currentDisplayedProcessTree = project.processTree;
    this.processTreeService.selectedRootNodeID = project.selectedRootNodeID;
    // this.variantService.variants = project.variants;
    this.variantFilterService.variantFilters = project.variantFilters;
    this.variantQueryService.variantQuery = project.variantQuery;
    this.variantService.clusteringConfig = project.clusteringConfiguration;
  }

  private replayLogModifications(logModifications: LogModification[]) {
    return logModifications.reduce(
      (previous, current) =>
        previous.pipe(
          tap(() => console.log('Replaying Log Modification:', current.type)),
          mergeMap(() => {
            switch (current.type) {
              case LogModificationType.ACTIVITY_DELETION:
                return this.variantService.deleteActivity(
                  (<ActivityDeletion>current).activityName
                );
              case LogModificationType.ACTIVITY_RENAMING:
                return this.variantService.renameActivity(
                  (<ActivityRenaming>current).activityName,
                  (<ActivityRenaming>current).newActivityName
                );
              case LogModificationType.VARIANT_DELETION:
                return this.variantService.deleteVariants(
                  (<VariantsDeletion>current).variantsBids
                );
              case LogModificationType.USER_DEFINED_VARIANT_ADDITION:
                return this.variantService.addUserDefinedVariant(
                  (<UserDefinedVariantAddition>current).variant
                );
              case LogModificationType.USER_DEFINED_INFIX_ADDITION:
                console.log((<UserDefinedInfixAddition>current).infix);
                console.log((<UserDefinedInfixAddition>current).infix.variant);
                return this.variantService.addInfixToBackend(
                  (<UserDefinedInfixAddition>current).infix
                );
            }
          })
        ),
      new Observable((subscriber) => {
        subscriber.next();
        subscriber.complete();
      })
    );
  }

  public async saveProject(askUserForPath: boolean = true) {
    const project = JSON.stringify(
      instanceToPlain(this.currentProject, {
        enableCircularCheck: true,
      })
    );

    if (askUserForPath) {
      const now = new Date();
      const datepipe: DatePipe = new DatePipe('en-US');
      const formattedDate = datepipe.transform(now, 'YYYY_MM_dd_HH_mm');

      const filePath = await this.electronService.showSaveDialog(
        `cortado_${
          this.logService.loadedEventLog.split('.')[0]
        }_${formattedDate}`,
        'json',
        new Blob([project]),
        'Save project',
        'Save Cortado Project'
      );
      if (filePath) this.latestSavedProject = JSON.parse(project);
      return filePath;
    } else {
      this.electronService.saveToUserFolder('latest_project', 'json', project);
    }
  }
}

class Project {
  public cortadoVersion: string;
  public eventlogPath: string;
  public timeGranularity: TimeUnit;
  @Transform(({ value, key, obj, type }) => {
    if (type === TransformationType.PLAIN_TO_CLASS) {
      const transformed = [];
      for (let logModification of value) {
        if (
          logModification.type ===
          LogModificationType.USER_DEFINED_VARIANT_ADDITION
        )
          transformed.push(
            plainToInstance(UserDefinedVariantAddition, logModification)
          );
        else if (
          logModification.type ===
          LogModificationType.USER_DEFINED_INFIX_ADDITION
        )
          transformed.push(
            plainToInstance(UserDefinedInfixAddition, logModification)
          );
        else transformed.push(logModification);
      }
      return transformed;
    }
    return value;
  })
  public logModifications: LogModification[];
  @Type(() => ProcessTree)
  public processTree: ProcessTree;
  @Type(() => ProcessTree)
  public processTreeHistory: ProcessTree[];
  public treeCacheIndex: number;
  public selectedRootNodeID: number;
  @Type(() => Variant)
  public variants: Variant[];
  @Transform(({ value, key, obj, type }) => {
    if (type === TransformationType.PLAIN_TO_CLASS) {
      let map = new Map<string, VariantFilter>();
      for (let entry of Object.entries(value))
        map.set(entry[0], plainToInstance(VariantFilter, entry[1]));
      return map;
    }
    return value;
  })
  public variantFilters: Map<string, VariantFilter>;
  public variantQuery: string;
  public clusteringConfiguration: ClusteringConfig;
  constructor(
    eventlogPath: string,
    timeGranularity: TimeUnit,
    logModifications: LogModification[],
    processTree: ProcessTree,
    processTreeHistory: ProcessTree[],
    treeCacheIndex: number,
    selectedRootNodeID: number,
    variants: Variant[],
    variantFilters: Map<string, VariantFilter>,
    variantQuery: string,
    clusteringConfiguration: ClusteringConfig,
    cortadoVersion: string = environment.VERSION
  ) {
    this.eventlogPath = eventlogPath;
    this.timeGranularity = timeGranularity;
    this.logModifications = logModifications;
    this.processTree = processTree;
    this.processTreeHistory = processTreeHistory;
    this.treeCacheIndex = treeCacheIndex;
    this.selectedRootNodeID = selectedRootNodeID;
    this.variants = variants;
    this.variantFilters = variantFilters;
    this.variantQuery = variantQuery;
    this.clusteringConfiguration = clusteringConfiguration;
    this.cortadoVersion = cortadoVersion;
  }
}
